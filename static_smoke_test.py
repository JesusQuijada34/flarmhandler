import ast
from pathlib import Path

source = Path("flarmhandler.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
assert "parse_Fluthin_url" in functions
assert "_safe_extract_member" in functions
assert "extract_archive" in functions
assert "z.extractall(base)" in source
assert "archive.extractall(base)" in source
assert "issym()" in source and "islnk()" in source
assert "flarmstore://" in source and "fluthinstore://" in source
assert "raise_for_status" in source
# Integración con el ecosistema Fluthin (iflapp v2 / asksome / mexf)
assert "parse_package_filename" in functions
assert "extract_archive" in functions
assert "ensure_executable_bits" in functions
assert "register_package_associations" in functions
assert "handle_mexf_file" in functions
assert "HAS_PACKAGE_LIBS" in source
print("FLARMHANDLER_STATIC_SECURITY_CHECK_OK")
