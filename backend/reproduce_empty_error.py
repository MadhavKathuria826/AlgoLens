from cpp_classifier import parse_cpp_ast
from cpp_interpreter import InterpreterError

code_a = """#include <map>

int test_map(int target_key) {
    std::map<int, int> m;
    m.insert(std::make_pair(100, 10));
    m.insert(std::make_pair(200, 20));
    bool found = (m.find(target_key) != m.end());
    if (found) return 1;
    return 0;
}"""

tu, header_count = parse_cpp_ast(code_a, True)
f = list(tu.cursor.get_children())[-1]
body = [c for c in f.get_children() if c.kind.name == 'COMPOUND_STMT'][0]
insert_stmt = list(body.get_children())[1] # m.insert(...)
c1 = list(insert_stmt.get_children())[1] # std::make_pair(...)
sub0 = list(c1.get_children())[0] # DECL_REF_EXPR std::make_pair

print("=== REPRODUCING EXACT EXCEPTION FROM COMMIT e185641 ===")
print("sub0 kind:", sub0.kind.name)
print("sub0 spelling:", repr(sub0.spelling))

# Commit e185641 DECL_REF_EXPR evaluation logic:
var_name = sub0.spelling # '' (empty string)
if var_name not in ("nullptr", "NULL"):
    # lookup('') -> False
    err = InterpreterError(f"Undefined variable '{var_name}'")
    print("\nEXACT ERROR REPRODUCED:")
    print("Exception Message:", repr(str(err)))
