"""
只有一个 bug 的小文件，作为 P0 的验收任务。

sum_items 的循环多跑了一次，空列表和普通列表都会 IndexError。
"""


def sum_items(items):
    total = 0
    for i in range(len(items) + 1):
        total += items[i]
    return total


if __name__ == "__main__":
    print(sum_items([1, 2, 3]))
