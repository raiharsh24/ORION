import os
import ast
import re
import json
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

def generate_date_str(file_path: str) -> str:
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.utcfromtimestamp(mtime).isoformat()
    except Exception:
        return datetime.utcnow().isoformat()

class LanguageParser(ABC):
    """
    Abstract base class defining the compiler AST analysis stage.
    """
    def __init__(self, workspace_root: str = "/home/warlock/ORION") -> None:
        self.workspace_root = workspace_root

    @abstractmethod
    def parse_file(self, file_path: str, code: str) -> Dict[str, Any]:
        """
        Parses source file content and returns a dictionary with extracted nodes and edges.
        """
        pass

class PythonParser(LanguageParser):
    """
    Extracts module dependencies, classes, inherits, API routes, and functions using Python AST.
    """
    def parse_file(self, file_path: str, code: str) -> Dict[str, Any]:
        nodes = []
        edges = []
        rel_path = os.path.relpath(file_path, self.workspace_root)
        file_id = f"file:{rel_path}"

        # Create base file node
        nodes.append({
            "id": file_id,
            "title": os.path.basename(file_path),
            "description": f"Python Source File: {rel_path}",
            "type": "code",
            "category": "Development",
            "tags": ["python", "source-code"],
            "metadata": {"path": rel_path, "language": "python"},
            "createdAt": generate_date_str(file_path),
            "updatedAt": generate_date_str(file_path),
            "importance": 0.4,
            "status": "HEALTHY"
        })

        try:
            tree = ast.parse(code)
            for item in ast.walk(tree):
                # Class declarations and inheritance
                if isinstance(item, ast.ClassDef):
                    class_id = f"class:{rel_path}#{item.name}"
                    bases = []
                    for base in item.bases:
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.append(base.attr)
                            
                    nodes.append({
                        "id": class_id,
                        "title": item.name,
                        "description": f"Python Class defined in {rel_path}",
                        "type": "class",
                        "category": "Development",
                        "tags": ["class", "python"],
                        "metadata": {"file": rel_path, "inherits": bases},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.3,
                        "status": "HEALTHY"
                    })
                    # Add containment link
                    edges.append({
                        "source": file_id,
                        "target": class_id,
                        "type": "containment",
                        "weight": 1.2
                    })
                    # Add inheritance links
                    for base_class in bases:
                        edges.append({
                            "source": class_id,
                            "target": f"class-ref:{base_class}",
                            "type": "inheritance",
                            "weight": 1.0
                        })

                # Function and route definitions
                elif isinstance(item, ast.FunctionDef):
                    # Check decorators for API routes
                    is_route = False
                    route_path = ""
                    for dec in item.decorator_list:
                        # Check Call decorator (@router.get("/foo"))
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                            if dec.func.attr in ("get", "post", "put", "delete", "patch"):
                                is_route = True
                                if dec.args and isinstance(dec.args[0], ast.Constant):
                                    route_path = dec.args[0].value
                        # Check Attribute decorator (@router.get)
                        elif isinstance(dec, ast.Attribute):
                            if dec.attr in ("get", "post", "put", "delete", "patch"):
                                is_route = True

                    func_id = f"func:{rel_path}#{item.name}"
                    if is_route:
                        nodes.append({
                            "id": func_id,
                            "title": f"{item.name} ({route_path})" if route_path else item.name,
                            "description": f"API Route handler in {rel_path}",
                            "type": "route",
                            "category": "Communication",
                            "tags": ["api-route", "python"],
                            "metadata": {"file": rel_path, "route_path": route_path},
                            "createdAt": generate_date_str(file_path),
                            "updatedAt": generate_date_str(file_path),
                            "importance": 0.5,
                            "status": "HEALTHY"
                        })
                    else:
                        nodes.append({
                            "id": func_id,
                            "title": item.name,
                            "description": f"Function defined in {rel_path}",
                            "type": "function",
                            "category": "Development",
                            "tags": ["function", "python"],
                            "metadata": {"file": rel_path},
                            "createdAt": generate_date_str(file_path),
                            "updatedAt": generate_date_str(file_path),
                            "importance": 0.25,
                            "status": "HEALTHY"
                        })
                    edges.append({
                        "source": file_id,
                        "target": func_id,
                        "type": "containment",
                        "weight": 1.2
                    })

                # Imports
                elif isinstance(item, ast.Import):
                    for name_alias in item.names:
                        edges.append({
                            "source": file_id,
                            "target": f"import-ref:{name_alias.name}",
                            "type": "dependency",
                            "weight": 0.8
                        })
                elif isinstance(item, ast.ImportFrom):
                    if item.module:
                        edges.append({
                            "source": file_id,
                            "target": f"import-ref:{item.module}",
                            "type": "dependency",
                            "weight": 0.8
                        })

        except Exception as e:
            logger.error(f"Python parser failed on '{file_path}': {str(e)}")

        return {"nodes": nodes, "edges": edges}

class TypeScriptParser(LanguageParser):
    """
    Invokes Node.js subprocess with the TypeScript Compiler API script to parse TypeScript files.
    """
    def __init__(self, workspace_root: str = "/home/warlock/ORION", parser_js_path: Optional[str] = None) -> None:
        super().__init__(workspace_root)
        if not parser_js_path:
            parser_js_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parse_ts_ast.js")
        self.parser_js_path = parser_js_path

    def parse_file(self, file_path: str, code: str) -> Dict[str, Any]:
        nodes = []
        edges = []
        rel_path = os.path.relpath(file_path, self.workspace_root)
        file_id = f"file:{rel_path}"

        # Create base file node
        nodes.append({
            "id": file_id,
            "title": os.path.basename(file_path),
            "description": f"TypeScript Source File: {rel_path}",
            "type": "code",
            "category": "Development",
            "tags": ["typescript", "source-code"],
            "metadata": {"path": rel_path, "language": "typescript"},
            "createdAt": generate_date_str(file_path),
            "updatedAt": generate_date_str(file_path),
            "importance": 0.4,
            "status": "HEALTHY"
        })

        try:
            # Spawn Node.js parser script
            res = subprocess.run(
                ["node", self.parser_js_path, file_path],
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                
                # Process imports
                for imp in data.get("imports", []):
                    if imp.startswith('.'):
                        # Relative project imports
                        dir_name = os.path.dirname(rel_path)
                        target_rel = os.path.normpath(os.path.join(dir_name, imp))
                        edges.append({
                            "source": file_id,
                            "target": f"file:{target_rel}",
                            "type": "dependency",
                            "weight": 1.0
                        })
                    else:
                        # Package imports
                        edges.append({
                            "source": file_id,
                            "target": f"dep:{imp}",
                            "type": "dependency",
                            "weight": 0.8
                        })

                # Process classes
                for cls in data.get("classes", []):
                    cls_name = cls["name"] if isinstance(cls, dict) else cls
                    class_id = f"class:{rel_path}#{cls_name}"
                    inherits = cls.get("extends", []) if isinstance(cls, dict) else []
                    impls = cls.get("implements", []) if isinstance(cls, dict) else []
                    
                    nodes.append({
                        "id": class_id,
                        "title": cls_name,
                        "description": f"TypeScript Class defined in {rel_path}",
                        "type": "class",
                        "category": "Development",
                        "tags": ["class", "typescript"],
                        "metadata": {"file": rel_path, "extends": inherits, "implements": impls},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.3,
                        "status": "HEALTHY"
                    })
                    edges.append({
                        "source": file_id,
                        "target": class_id,
                        "type": "containment",
                        "weight": 1.2
                    })
                    
                    for parent in inherits:
                        edges.append({
                            "source": class_id,
                            "target": f"class-ref:{parent}",
                            "type": "inheritance",
                            "weight": 1.0
                        })
                    for interface in impls:
                        edges.append({
                            "source": class_id,
                            "target": f"interface-ref:{interface}",
                            "type": "implementation",
                            "weight": 1.0
                        })

                # Process interfaces
                for inter in data.get("interfaces", []):
                    inter_id = f"interface:{rel_path}#{inter}"
                    nodes.append({
                        "id": inter_id,
                        "title": inter,
                        "description": f"TypeScript Interface defined in {rel_path}",
                        "type": "interface",
                        "category": "Development",
                        "tags": ["interface", "typescript"],
                        "metadata": {"file": rel_path},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.25,
                        "status": "HEALTHY"
                    })
                    edges.append({
                        "source": file_id,
                        "target": inter_id,
                        "type": "containment",
                        "weight": 1.2
                    })

                # Process enums
                for en in data.get("enums", []):
                    enum_id = f"enum:{rel_path}#{en}"
                    nodes.append({
                        "id": enum_id,
                        "title": en,
                        "description": f"TypeScript Enum defined in {rel_path}",
                        "type": "class",
                        "category": "Development",
                        "tags": ["enum", "typescript"],
                        "metadata": {"file": rel_path},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.25,
                        "status": "HEALTHY"
                    })
                    edges.append({
                        "source": file_id,
                        "target": enum_id,
                        "type": "containment",
                        "weight": 1.1
                    })

                # Process react components and hooks
                for rc in data.get("reactComponents", []):
                    rc_id = f"rc:{rel_path}#{rc}"
                    nodes.append({
                        "id": rc_id,
                        "title": rc,
                        "description": f"React Component defined in {rel_path}",
                        "type": "class",
                        "category": "Development",
                        "tags": ["react-component", "typescript"],
                        "metadata": {"file": rel_path},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.35,
                        "status": "HEALTHY"
                    })
                    edges.append({
                        "source": file_id,
                        "target": rc_id,
                        "type": "containment",
                        "weight": 1.2
                    })

                for hk in data.get("hooks", []):
                    hk_id = f"hook:{rel_path}#{hk}"
                    nodes.append({
                        "id": hk_id,
                        "title": hk,
                        "description": f"React Hook defined in {rel_path}",
                        "type": "function",
                        "category": "Development",
                        "tags": ["react-hook", "typescript"],
                        "metadata": {"file": rel_path},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.3,
                        "status": "HEALTHY"
                    })
                    edges.append({
                        "source": file_id,
                        "target": hk_id,
                        "type": "containment",
                        "weight": 1.1
                    })

                # Process normal functions
                for fn in data.get("functions", []):
                    fn_id = f"func:{rel_path}#{fn}"
                    nodes.append({
                        "id": fn_id,
                        "title": fn,
                        "description": f"Function defined in {rel_path}",
                        "type": "function",
                        "category": "Development",
                        "tags": ["function", "typescript"],
                        "metadata": {"file": rel_path},
                        "createdAt": generate_date_str(file_path),
                        "updatedAt": generate_date_str(file_path),
                        "importance": 0.25,
                        "status": "HEALTHY"
                    })
                    edges.append({
                        "source": file_id,
                        "target": fn_id,
                        "type": "containment",
                        "weight": 1.1
                    })
            else:
                logger.error(f"TypeScript parser subprocess failed for '{file_path}': {res.stderr}")
        except Exception as e:
            logger.error(f"TypeScript parser execution failed on '{file_path}': {str(e)}")

        return {"nodes": nodes, "edges": edges}

class MarkdownParser(LanguageParser):
    """
    Extracts tags, frontmatter descriptions, wikilinks, and headers from markdown documents.
    """
    def parse_file(self, file_path: str, code: str) -> Dict[str, Any]:
        nodes = []
        edges = []
        rel_path = os.path.relpath(file_path, self.workspace_root)
        file_id = f"file:{rel_path}"

        # Default title is the base file name
        title = os.path.basename(file_path)
        tags = ["document"]
        description = f"Markdown Document: {rel_path}"

        # 1. Frontmatter parsing
        try:
            fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', code, re.DOTALL | re.MULTILINE)
            if fm_match:
                fm_text = fm_match.group(1)
                # Quick regex extractions for tags & title without importing third party yaml parsers
                tag_match = re.search(r'tags:\s*\[(.*?)\]', fm_text)
                if tag_match:
                    tags.extend([t.strip().strip("'\"") for t in tag_match.group(1).split(",")])
                else:
                    # Single tag format (e.g. tag: some-tag)
                    single_tag = re.search(r'tag:\s*(\S+)', fm_text)
                    if single_tag:
                        tags.append(single_tag.group(1).strip())
                        
                title_match = re.search(r'title:\s*["\']?([^"\'\n]+)["\']?', fm_text)
                if title_match:
                    title = title_match.group(1).strip()
                desc_match = re.search(r'description:\s*["\']?([^"\'\n]+)["\']?', fm_text)
                if desc_match:
                    description = desc_match.group(1).strip()
        except Exception:
            pass

        # Parse main title if not set in frontmatter
        if title == os.path.basename(file_path):
            main_h1 = re.search(r'^#\s+(.+)$', code, re.MULTILINE)
            if main_h1:
                title = main_h1.group(1).strip()

        # Build node type categorizations
        is_research = "research/" in rel_path or "research" in tags
        node_type = "research" if is_research else "document"
        category = "Research" if is_research else "Documents"
        if rel_path in ("FRIDAY.md", "CLAUDE.md", "README.md"):
            node_type = "manifest"
            category = "Manifest"

        nodes.append({
            "id": file_id,
            "title": title,
            "description": description,
            "type": node_type,
            "category": category,
            "tags": list(set(tags)),
            "metadata": {"path": rel_path},
            "createdAt": generate_date_str(file_path),
            "updatedAt": generate_date_str(file_path),
            "importance": 0.6 if node_type == "manifest" else 0.4,
            "status": "HEALTHY"
        })

        # 2. Extract [[Wikilinks]]
        wikilinks = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', code)
        for w in wikilinks:
            clean_w = w.strip()
            edges.append({
                "source": file_id,
                "target": f"wikilink:{clean_w.lower()}",
                "type": "documentation",
                "weight": 1.0,
                "metadata": {"label": clean_w}
            })

        # 3. Extract standard Markdown links e.g. [docs](path/to/doc.md)
        md_links = re.findall(r'\[[^\]]+\]\(([^)]+\.md)\)', code)
        for mdl in md_links:
            # Skip web URLs
            if mdl.startswith(('http://', 'https://')):
                continue
            dir_name = os.path.dirname(rel_path)
            target_rel = os.path.normpath(os.path.join(dir_name, mdl))
            edges.append({
                "source": file_id,
                "target": f"file:{target_rel}",
                "type": "documentation",
                "weight": 1.0
            })

        return {"nodes": nodes, "edges": edges}
