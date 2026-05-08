with open("routes/admin/common.py", "r") as f:
    code = f.read()

code = code.replace("from utils.db import get_db", "from utils.mongo_mock import MockDb")
code = code.replace("db = get_db()", "db = MockDb()")

with open("routes/admin/common.py", "w") as f:
    f.write(code)
print("common.py patched with MockDb!")
