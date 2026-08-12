import ast
from pathlib import Path


MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"


def _parse_main() -> ast.Module:
    return ast.parse(MAIN_PATH.read_text())


def _is_app_include_router_expr(node: ast.AST, router_name: str) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    call = node.value
    if not isinstance(call.func, ast.Attribute):
        return False
    if not (
        isinstance(call.func.value, ast.Name)
        and call.func.value.id == "app"
        and call.func.attr == "include_router"
    ):
        return False
    if not call.args or not isinstance(call.args[0], ast.Attribute):
        return False
    router = call.args[0]
    return isinstance(router.value, ast.Name) and router.value.id == router_name and router.attr == "router"


def _contains_deep_research_master_flag_gate(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.If):
            continue
        test = child.test
        if isinstance(test, ast.Name) and test.id == "DEEP_RESEARCH_ENABLED":
            return True
        if (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Name)
            and test.operand.id == "DEEP_RESEARCH_ENABLED"
        ):
            return True
    return False


def test_core_deep_research_routes_are_unconditionally_registered():
    parsed = _parse_main()

    assert _contains_deep_research_master_flag_gate(parsed) is False
    assert any(_is_app_include_router_expr(node, "crawl") for node in parsed.body)
    assert any(_is_app_include_router_expr(node, "research_claims") for node in parsed.body)
    assert any(_is_app_include_router_expr(node, "deep_research") for node in parsed.body)
