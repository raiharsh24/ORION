import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

from app.intent.types import IntentType
from app.intent.events import IntentAnalyzed


@dataclass
class IntentResult:
    intent: IntentType = IntentType.UNKNOWN
    confidence: float = 0.0
    reasoning: str = ""


PatternWeight = Tuple[re.Pattern, float]


class RuleBasedIntentAnalyzer:
    def __init__(self, event_bus=None):
        self._event_bus = event_bus
        self._running = False
        self._patterns: Dict[IntentType, List[PatternWeight]] = self._build_patterns()

    async def start(self):
        self._running = True
        logger.info("RuleBasedIntentAnalyzer started.")

    async def shutdown(self):
        self._running = False
        logger.info("RuleBasedIntentAnalyzer shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "intent_count": len(self._patterns),
                "pattern_count": sum(len(ps) for ps in self._patterns.values()),
            },
        }

    async def analyze(self, request: str) -> IntentResult:
        result = self._sync_analyze(request)
        if self._running and self._event_bus:
            try:
                event = IntentAnalyzed(request, result.intent, result.confidence, result.reasoning)
                await self._event_bus.publish(event)
            except Exception as e:
                logger.error(f"Failed to publish IntentAnalyzed event: {e}")
        return result

    def _sync_analyze(self, request: str) -> IntentResult:
        text = request.lower().strip()
        if not text:
            return IntentResult(IntentType.UNKNOWN, 1.0, "Empty request")

        scores: Dict[IntentType, float] = {}
        matched_any = False
        for intent, patterns in self._patterns.items():
            score = 0.0
            for pattern, weight in patterns:
                matches = pattern.findall(text)
                if matches:
                    score += weight * len(matches)
                    matched_any = True
            if score > 0:
                scores[intent] = score

        if not matched_any:
            return IntentResult(IntentType.UNKNOWN, 0.5, "No patterns matched")

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        confidence = min(best_score / 10.0, 1.0)

        matched_intents = sorted(scores.items(), key=lambda x: -x[1])
        detail = "; ".join(f"{k.value}={v:.1f}" for k, v in matched_intents[:3])
        reasoning = f"Best={best_intent.value}({best_score:.1f}) among [{detail}]"

        return IntentResult(intent=best_intent, confidence=confidence, reasoning=reasoning)

    @staticmethod
    def _build_patterns() -> Dict[IntentType, List[PatternWeight]]:
        _r = re.compile

        return {
            IntentType.CONVERSATION: [
                (_r(r"\b(hello|hi\b|hey\b|greetings|good morning|good evening|good afternoon)\b"), 1.5),
                (_r(r"\b(how are you|how('s| is) it going|what('s| is) up|how do you do)\b"), 2.0),
                (_r(r"\b(thanks|thank you|thankyou|appreciate it|much appreciated)\b"), 1.5),
                (_r(r"\b(bye\b|goodbye|see you|later|talk to you soon)\b"), 1.5),
                (_r(r"\b(you('re| are) welcome|my pleasure|happy to help)\b"), 2.0),
                (_r(r"\b(yes|no|maybe|sure|okay|ok\b|alright|cool\b|nice\b|great\b|awesome|perfect)\b"), 0.5),
                (_r(r"\b(i think|i feel|i believe|in my opinion|personally)\b"), 1.0),
                (_r(r"\b(who are you|what are you|what can you do|tell me about yourself)\b"), 2.5),
                (_r(r"\b(how('s| is) your day|are you (busy|free|there)|can you help me)\b"), 1.5),
                (_r(r"\b(sorry|apologies|my bad|excuse me|pardon)\b"), 1.0),
                (_r(r"\b(just (saying|checking|wondering|curious))\b"), 1.0),
                (_r(r"\b(what('s| is) new|what('s| is) up|how (are|have) you been)\b"), 1.5),
            ],

            IntentType.CODING: [
                (_r(r"\b(code|coding|programming|software)\b"), 2.0),
                (_r(r"\b(function|method|class\b|object|variable|constant)\b"), 2.5),
                (_r(r"\b(bug|debug|debugging|error|exception|crash|stack trace|traceback)\b"), 2.5),
                (_r(r"\b(tests?|testing|unit test|integration test|pytest|unittest|tdd)\b"), 2.0),
                (_r(r"\b(refactor|refactoring|rewrite|rearchitect|redesign)\b"), 2.5),
                (_r(r"\b(commit|merge|pull request|pr\b|branch|git\b|push|rebase|clone|checkout)\b"), 2.5),
                (_r(r"\b(import |export |require|from .* import)\b"), 2.0),
                (_r(r"\b(def |class |async |await |yield |lambda)\b"), 3.0),
                (_r(r"\b(apis?|endpoints?|routes?|middleware|rest\b|graphql|grpc)\b"), 2.0),
                (_r(r"\b(database|sql\b|query|orm|schema|migration|table|index)\b"), 2.0),
                (_r(r"\b(docker|container|kubernetes|k8s|deploy|ci\b|cd\b|jenkins|github action)\b"), 2.5),
                (_r(r"\b(npm |pip |go get|cargo|maven|gradle|nuget|yarn |bundle)\b"), 2.5),
                (_r(r"\b(compile|compiler|build\b|syntax|lint|linter|type (check|hint)|annotation)\b"), 2.5),
                (_r(r"\b(python|javascript|typescript|rust\b|go\b|java|cpp\b|c\+\+|ruby|php\b|swift|kotlin)\b"), 2.0),
                (_r(r"\b(fix|fixing|broken|doesn't work|not working|issue|problem|buggy)\b.*\b(code|function|app|program)\b"), 3.0),
                (_r(r"\b(write|implement|create|build\b|develop)\b.*\b(function|class|module|script|program|test|code|api|algorithm)\b"), 2.5),
                (_r(r"\b(implement|implementation)\b"), 2.0),
                (_r(r"[{}();=<>+\-*/%&|^~]"), 0.5),
            ],

            IntentType.TERMINAL: [
                (_r(r"\b(terminal|shell|command line|cli\b|console)\b"), 3.0),
                (_r(r"\b(bash\b|zsh\b|sh\b|fish\b|powershell|cmd\b|prompt)\b"), 3.0),
                (_r(r"\b(run\b|execute)\b.*\b(command|script|program)\b"), 2.5),
                (_r(r"\b(ls\b|cd\b|pwd\b|mkdir|rmdir|rm\b|cp\b|mv\b|chmod|chown|grep|find\b|cat\b|less\b|head\b|tail\b|sort|uniq|wc\b)\b"), 3.0),
                (_r(r"\b(ps\b|top\b|htop|kill\b|pkill|nohup|bg\b|fg\b|jobs\b)\b"), 3.0),
                (_r(r"\b(ssh\b|scp\b|rsync|curl\b|wget\b|ping\b|traceroute|netstat|ss\b|ifconfig|ip\b)\b"), 3.0),
                (_r(r"\b(use|run)\b.*\b(curl|ssh|scp|rsync|wget|ping)\b"), 3.5),
                (_r(r"\b(pipe|redirect|grep|awk\b|sed\b|xargs|tee\b|cut\b|tr\b|diff\b|patch)\b"), 2.5),
                (_r(r"\b(alias|export|source|env\b|which\b|whereis|whatis|man\b)\b"), 2.5),
                (_r(r"\b(nano|vim\b|vi\b|emacs|neovim)\b"), 3.0),
                (_r(r"\b(nano|vim\b|vi\b|emacs|neovim)\b.*\b(file|config|\.\w+)\b"), 3.5),
            ],

            IntentType.DESKTOP: [
                (_r(r"\b(open\b)\b.*\b(app|application|folder|directory|file\b|browser|settings|terminal)\b"), 3.5),
                (_r(r"\b(desktop|workspace|window|minimize|maximize|close)\b"), 2.5),
                (_r(r"\b(switch to|alt tab|focus on|bring to front)\b"), 2.5),
                (_r(r"\b(screenshot|screen\b|display|monitor)\b.*\b(take|capture|record)\b"), 3.0),
                (_r(r"\b(take|capture|record)\b.*\b(screenshot|snapshot)\b"), 3.0),
                (_r(r"\b(system (tray|notification|setting|preference))\b"), 2.0),
                (_r(r"\b(mouse|keyboard|click |double.?click|right.?click|drag|drop|scroll)\b"), 2.5),
                (_r(r"\b(notification|toast|alert|popup|dialog)\b"), 2.0),
                (_r(r"\b(file manager|explorer|finder|nautilus|dolphin|thunar)\b"), 2.5),
                (_r(r"\b(volume|brightness|wifi|bluetooth|airplane mode|dark mode|night light)\b"), 2.0),
                (_r(r"\b(sleep|hibernate|shutdown|restart|reboot|lock|log out|sign out)\b"), 2.5),
            ],

            IntentType.BROWSER: [
                (_r(r"\b(search|google|bing|duckduckgo|yahoo)\b.*\b(for|the)\b"), 3.0),
                (_r(r"\b(navigate|go\b|open|browse)\b.*\b(to\b|url|website|site|page|link)\b"), 3.0),
                (_r(r"\b(browser|chrome|firefox|safari|edge|opera|brave)\b"), 2.5),
                (_r(r"\b(url\b|http[s]?://|www\.|\.com\b|\.org\b|\.net\b|\.io\b)\b"), 3.0),
                (_r(r"\b(browse|surf|internet|web\b|online)\b"), 2.5),
                (_r(r"\b(download|upload)\b.*\b(file|from|to)\b"), 2.0),
                (_r(r"\b(bookmark|favorite|history|tab\b|window)\b.*\b(browser|chrome|firefox)\b"), 2.5),
            ],

            IntentType.WORKFLOW: [
                (_r(r"\b(workflow|pipeline|chain|sequence)\b"), 4.5),
                (_r(r"\b(automate|automation|auto\b|scheduled)\b"), 2.5),
                (_r(r"\b(when|if)\b.*\b(then|trigger|automatically)\b"), 2.5),
                (_r(r"\b(trigger|event.?driven|reactive)\b"), 2.5),
                (_r(r"\b(step|stage|phase)\b.*\b(1|2|3|first|second|third|next|final)\b"), 2.0),
                (_r(r"\b(cron|schedule|timer|every (day|hour|minute|week|month))\b"), 2.5),
                (_r(r"\b(ci|cd)\b.*\b(pipeline|workflow|automation)\b"), 4.0),
                (_r(r"\b(iftt|zapier|make\.com|n8n|temporal|camunda)\b"), 3.0),
                (_r(r"\b(recipe|routine|macro)\b"), 2.0),
            ],

            IntentType.PLANNING: [
                (_r(r"\b(plan|planning|strategy|strategic)\b"), 2.5),
                (_r(r"\b(roadmaps?|timelines?|milestones?|deadlines?)\b"), 2.5),
                (_r(r"\b(goals?|objectives?|targets?|aims?|purposes?)\b"), 2.0),
                (_r(r"\b(sprint|epic|story|task|backlog|ticket|jira|linear|asana|trello)\b"), 2.5),
                (_r(r"\b(prioritize|priority|critical|blocker|urgent|important)\b"), 2.0),
                (_r(r"\b(okrs?|kpis?|metrics?|measures?|tracks?|progress)\b"), 3.0),
                (_r(r"\b(project (plan|management|scope|charter))\b"), 2.5),
                (_r(r"\b(phase|iteration|release|version|v?\d+\.\d+)\b"), 2.0),
                (_r(r"\b(brainstorm|ideate|design|architecture|propose|proposal)\b"), 2.0),
            ],

            IntentType.MEMORY: [
                (_r(r"\b(remember|recall|forget|remind)\b"), 3.0),
                (_r(r"\b(what did (i|we)|what was|what were|what have)\b.*\b(before|earlier|previously|last|said|done|talked)\b"), 3.0),
                (_r(r"\b(save|store|keep|hold)\b.*\b(this|that|note|info|data|context)\b"), 2.5),
                (_r(r"\b(as (i|we) (said|mentioned|noted|discussed))\b"), 2.5),
                (_r(r"\b(you (said|told|mentioned|noted|promised))|(i (told|said))\b"), 3.0),
                (_r(r"\b(yesterday|earlier|before|later|next time)\b.*\b(said|mentioned|discussed|talked|told|refactor|update|change)\b"), 2.5),
                (_r(r"\b(don't forget|note that|keep in mind|bearing in mind)\b"), 2.5),
                (_r(r"\b(recall|retrieve|fetch)\b.*\b(from|memory|context|history)\b"), 3.0),
                (_r(r"\b(previous|prior|last) (conversation|session|chat|discussion)\b"), 2.5),
                (_r(r"\b(context|history|background)\b"), 1.5),
            ],

            IntentType.SEARCH: [
                (_r(r"\b(search|find|locate|lookup|look up|seek)\b"), 2.5),
                (_r(r"\b(how to|how do (i|you)|how can (i|we))\b"), 2.5),
                (_r(r"\b(what is|what are|what does|whats|who is|who are|when is|where is)\b"), 2.0),
                (_r(r"\b(tell me about|information (on|about)|details (on|about)|explain)\b"), 2.5),
                (_r(r"\b(define|definition|meaning|wiki|wikipedia|docs|documentation)\b"), 2.5),
                (_r(r"\b(query|retrieve|fetch)\b.*\b(data|info|record|result)\b"), 2.5),
                (_r(r"\b(get me|show me|find me|list\b)\b"), 2.5),
                (_r(r"\b(recommend|suggest|best|top|compare|vs\b|versus)\b"), 1.5),
                (_r(r"\b(tutorials?|guides?|examples?|samples?|recipes?|cheat sheets?)\b"), 2.5),
            ],

            IntentType.VISION: [
                (_r(r"\b(image|picture|photo|photograph|snapshot)\b"), 3.0),
                (_r(r"\b(screenshot|screen (capture|grab|record))\b"), 3.0),
                (_r(r"\b(see\b|look at|view|watch|observe)\b.*\b(this|that|the|image|picture|screen|photo)\b"), 3.0),
                (_r(r"\b(visual|vision|visually|sight)\b"), 2.5),
                (_r(r"\b(detect|recognize|identify)\b.*\b(object|face|text|pattern|shape|color)\b"), 3.0),
                (_r(r"\b(ocr|optical character|read|extract)\b.*\b(text|image|screen|picture)\b"), 3.0),
                (_r(r"\b(describe|analyze)\b.*\b(image|picture|photo|scene|screenshot)\b"), 3.0),
                (_r(r"\b(what do you see|what('s| is) in|can you see)\b"), 3.0),
                (_r(r"\b(camera|webcam|video|record|stream)\b"), 2.0),
            ],
        }
