"""
Workflow Runner — async execution loop for a single workflow run.

Handles all execution patterns:
  - Sequential step-by-step execution
  - Parallel fan-out for independent nodes
  - Conditional branching via on_success / on_failure edges
  - Loop nodes (repeating up to loop_max times)
  - Delay nodes (via executor)
  - Retry on failure (up to max_retries per node)
  - Pause / resume check points at each step boundary

The runner operates on a single Workflow + WorkflowRun pair.
WorkflowEngine owns multiple runners (one per active workflow).
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from loguru import logger

from app.workflow.workflow import (
    Workflow, WorkflowNode, WorkflowNodeStatus,
    WorkflowStatus, WorkflowFlowType, WorkflowNodeType
)
from app.workflow.graph import get_runnable_nodes, get_parallel_groups, get_next_node, propagate_statuses
from app.workflow.variables import merge_outputs
from app.workflow.executor import WorkflowNodeExecutor
from app.workflow.history import WorkflowHistory, WorkflowRun, WorkflowRunStatus


class WorkflowRunner:
    """
    Drives the async execution loop for a single workflow run.

    Lifecycle:
      start()  → spins up the asyncio task
      pause()  → sets the pause flag; loop yields at next safe checkpoint
      resume() → clears the pause flag
      cancel() → cancels the asyncio task and cleans up
    """

    def __init__(
        self,
        workflow: Workflow,
        run: WorkflowRun,
        executor: WorkflowNodeExecutor,
        history: WorkflowHistory,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._workflow   = workflow
        self._run        = run
        self._executor   = executor
        self._history    = history
        self._event_bus  = event_bus

        self._task: Optional[asyncio.Task] = None
        self._paused  = False
        self._cancelled = False

        # Tracks which nodes are currently in-flight (parallel execution)
        self._in_flight: Set[str] = set()

    # -----------------------------------------------------------------------
    # Public control surface
    # -----------------------------------------------------------------------

    def start(self) -> asyncio.Task:
        """Creates and returns the asyncio task driving the execution loop."""
        self._task = asyncio.create_task(self._run_loop(), name=f"wf_runner_{self._workflow.id}")
        return self._task

    def pause(self) -> None:
        """Signals the runner to pause at the next safe checkpoint."""
        self._paused = True
        self._workflow.status = WorkflowStatus.PAUSED
        self._run.status = WorkflowRunStatus.PAUSED
        logger.info(f"[Runner] Workflow '{self._workflow.id}' paused.")

    def resume(self) -> None:
        """Clears the pause flag so the loop continues."""
        self._paused = False
        self._workflow.status = WorkflowStatus.RUNNING
        self._run.status = WorkflowRunStatus.RUNNING
        logger.info(f"[Runner] Workflow '{self._workflow.id}' resumed.")

    def cancel(self) -> None:
        """Cancels the execution task."""
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()
        self._workflow.status = WorkflowStatus.CANCELLED
        self._run.status = WorkflowRunStatus.CANCELLED
        self._history.finish_run(self._run, WorkflowRunStatus.CANCELLED)
        logger.info(f"[Runner] Workflow '{self._workflow.id}' cancelled.")

    # -----------------------------------------------------------------------
    # Main execution loop
    # -----------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """
        Main async execution loop.

        Iterates until:
          - All nodes are in a terminal state (COMPLETED / FAILED / CANCELLED)
          - Workflow is explicitly cancelled
          - An unrecoverable error is raised
        """
        self._workflow.status = WorkflowStatus.RUNNING
        self._run.status = WorkflowRunStatus.RUNNING
        self._history.save_run(self._run)

        await self._emit("WorkflowStarted", {
            "workflow_id":   self._workflow.id,
            "workflow_name": self._workflow.name,
            "run_id":        self._run.run_id,
        })

        try:
            while not self._cancelled:
                # ----------------------------------------------------------
                # Pause checkpoint
                # ----------------------------------------------------------
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.2)

                if self._cancelled:
                    break

                # ----------------------------------------------------------
                # Determine runnable nodes
                # ----------------------------------------------------------
                runnable = get_runnable_nodes(self._workflow)
                if not runnable:
                    # Check if we are truly done or stuck
                    if self._all_terminal():
                        break
                    # Still waiting for in-flight parallel nodes
                    await asyncio.sleep(0.1)
                    continue

                # ----------------------------------------------------------
                # Parallel fan-out
                # ----------------------------------------------------------
                parallel_groups = get_parallel_groups(self._workflow)
                tasks = []
                for group in parallel_groups:
                    group_nodes = [
                        self._workflow.nodes[nid]
                        for nid in group
                        if nid in self._workflow.nodes
                        and self._workflow.nodes[nid].status == WorkflowNodeStatus.PENDING
                    ]
                    for node in group_nodes:
                        if node.id not in self._in_flight:
                            tasks.append(asyncio.create_task(
                                self._execute_node(node),
                                name=f"wf_node_{node.id}"
                            ))
                            self._in_flight.add(node.id)

                if tasks:
                    # Wait for at least one to complete before re-evaluating
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in done:
                        exc = t.exception()
                        if exc and not isinstance(exc, asyncio.CancelledError):
                            logger.error(f"[Runner] Task error: {exc}")
                else:
                    await asyncio.sleep(0.05)

            # ----------------------------------------------------------------
            # Determine terminal status
            # ----------------------------------------------------------------
            if self._cancelled:
                self._history.finish_run(self._run, WorkflowRunStatus.CANCELLED)
            elif any(
                n.status == WorkflowNodeStatus.FAILED
                for n in self._workflow.nodes.values()
            ):
                self._workflow.status = WorkflowStatus.FAILED
                self._run.error = "One or more nodes failed."
                self._history.finish_run(self._run, WorkflowRunStatus.FAILED, self._run.error)
            else:
                self._workflow.status = WorkflowStatus.COMPLETED
                self._history.finish_run(self._run, WorkflowRunStatus.COMPLETED)

        except asyncio.CancelledError:
            self._workflow.status = WorkflowStatus.CANCELLED
            self._history.finish_run(self._run, WorkflowRunStatus.CANCELLED)
            raise
        except Exception as e:
            logger.error(f"[Runner] Workflow '{self._workflow.id}' loop error: {e}")
            self._workflow.status = WorkflowStatus.FAILED
            self._history.finish_run(self._run, WorkflowRunStatus.FAILED, str(e))

        await self._emit("WorkflowFinished", {
            "workflow_id":   self._workflow.id,
            "workflow_name": self._workflow.name,
            "run_id":        self._run.run_id,
            "status":        self._workflow.status.value,
        })

    # -----------------------------------------------------------------------
    # Single node execution (with retry, loop, delay, conditional routing)
    # -----------------------------------------------------------------------

    async def _execute_node(self, node: WorkflowNode) -> None:
        """
        Executes a single node end-to-end:
          1. Mark RUNNING
          2. Handle DELAY flow type
          3. Execute via WorkflowNodeExecutor
          4. Merge outputs
          5. On failure: retry if max_retries > 0
          6. On LOOP flow type: re-pend the node if loop_max not reached
          7. On CONDITION: record branch decision
          8. Mark COMPLETED / FAILED
          9. Emit telemetry
        """
        node.status = WorkflowNodeStatus.RUNNING
        node.started_at = datetime.now(timezone.utc).isoformat()
        self._run.current_node_id = node.id
        self._history.save_run(self._run)

        await self._emit("WorkflowNodeStarted", {
            "workflow_id": self._workflow.id,
            "node_id":     node.id,
            "node_name":   node.name,
            "node_type":   node.type,
            "run_id":      self._run.run_id,
        })

        # Pre-delay for DELAY flow type nodes
        if node.flow_type == WorkflowFlowType.DELAY and node.delay_seconds > 0:
            logger.info(f"[Runner] Delay node '{node.id}' — waiting {node.delay_seconds}s")
            node.status = WorkflowNodeStatus.WAITING
            await asyncio.sleep(node.delay_seconds)
            node.status = WorkflowNodeStatus.RUNNING

        success = False
        outputs: Dict[str, Any] = {}

        for attempt in range(node.max_retries + 1):
            if attempt > 0:
                node.status = WorkflowNodeStatus.RETRYING
                node.retry_count = attempt
                self._run.retry_counts[node.id] = attempt
                self._run.total_retries += 1
                self._history.save_run(self._run)
                logger.info(
                    f"[Runner] Retrying node '{node.id}' "
                    f"attempt {attempt}/{node.max_retries}"
                )
                await asyncio.sleep(1.0)  # brief back-off between retries
                node.status = WorkflowNodeStatus.RUNNING

            try:
                outputs = await self._executor.execute_node(node, self._workflow)
                success = True
                break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                node.error = str(e)
                logger.warning(
                    f"[Runner] Node '{node.id}' attempt {attempt + 1} failed: {e}"
                )
                if attempt >= node.max_retries:
                    break  # out of retries

        # ------------------------------------------------------------------
        # Post-execution: persist outputs, mark status, handle edges
        # ------------------------------------------------------------------
        node.finished_at = datetime.now(timezone.utc).isoformat()

        if success:
            merge_outputs(self._workflow, node, outputs)

            # Handle CONDITION node branching
            if node.type in ("Condition", WorkflowNodeType.CONDITION.value):
                condition_result = outputs.get("condition_result", True)
                next_node = get_next_node(node, bool(condition_result), self._workflow)
                branch = "on_success" if condition_result else "on_failure"
                self._history.record_branch(
                    self._run, node.id, bool(condition_result), branch,
                    next_node.id if next_node else None
                )
                # Mark nodes NOT on the chosen branch as SKIPPED
                all_branches = {node.on_success, node.on_failure} - {None}
                taken_id = next_node.id if next_node else None
                for bid in all_branches:
                    if bid and bid != taken_id and bid in self._workflow.nodes:
                        self._workflow.nodes[bid].status = WorkflowNodeStatus.SKIPPED

            # Handle LOOP flow type
            if node.flow_type == WorkflowFlowType.LOOP:
                node.loop_count += 1
                if node.loop_count < node.loop_max:
                    # Reset status to re-run in next loop iteration
                    logger.info(
                        f"[Runner] Loop node '{node.id}' iteration "
                        f"{node.loop_count}/{node.loop_max}"
                    )
                    node.status = WorkflowNodeStatus.PENDING
                    self._in_flight.discard(node.id)
                    return  # will be picked up again by the main loop

            node.status = WorkflowNodeStatus.COMPLETED
            self._history.mark_node_completed(self._run, node.id)
        else:
            node.status = WorkflowNodeStatus.FAILED
            self._history.mark_node_failed(self._run, node.id, node.error or "Unknown error")

        self._in_flight.discard(node.id)
        self._workflow.updated_at = datetime.now(timezone.utc)
        self._history.save_run(self._run)

        await self._emit("WorkflowNodeFinished", {
            "workflow_id": self._workflow.id,
            "node_id":     node.id,
            "node_name":   node.name,
            "status":      node.status.value,
            "outputs":     outputs,
            "run_id":      self._run.run_id,
        })

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _all_terminal(self) -> bool:
        """Returns True when every node is in a terminal state."""
        terminal = {
            WorkflowNodeStatus.COMPLETED,
            WorkflowNodeStatus.FAILED,
            WorkflowNodeStatus.CANCELLED,
            WorkflowNodeStatus.SKIPPED,
        }
        return all(n.status in terminal for n in self._workflow.nodes.values())

    async def _emit(self, topic: str, data: Dict[str, Any]) -> None:
        """Publishes a workflow lifecycle event to the EventBus."""
        if self._event_bus:
            try:
                from app.events.events import OrionEvent
                await self._event_bus.publish(OrionEvent(topic, data))
            except Exception as e:
                logger.warning(f"[Runner] Failed to emit event '{topic}': {e}")

