"""验收测试：修好 hello.py 之后应该全部通过。"""

from hello import sum_items

assert sum_items([1, 2, 3]) == 6, "普通列表"
assert sum_items([]) == 0, "空列表"
assert sum_items([-1, 1]) == 0, "负数"

print("ok: 所有断言通过")
