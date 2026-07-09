import json_repair
print(type(json_repair.loads("Hello { \"a\": 1 }")))
print(json_repair.loads("Hello { \"a\": 1 }"))
