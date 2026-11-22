from itertools import product


def compatible(order, roll):
    return order["fabric"] == roll["fabric"] and order["width"] <= roll["width"]


def counts_key(vector, orders):
    urgent = sum(count for count, order in zip(vector, orders) if order["priority"] == "急")
    return urgent, sum(vector) - urgent, sum(count * order["length"] for count, order in zip(vector, orders))


def add(left, right):
    return tuple(a + b for a, b in zip(left, right))


def within(vector, maximum):
    return all(count <= limit for count, limit in zip(vector, maximum))


def piece_vectors(orders, kerf):
    maximum = tuple(order["quantity"] for order in orders)
    costs = tuple(order["length"] + kerf for order in orders)
    vectors = [(vector, sum(count * cost for count, cost in zip(vector, costs)))
               for vector in product(*(range(count + 1) for count in maximum))]
    return maximum, vectors
