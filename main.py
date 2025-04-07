import time


def heavy_computation():
    """
    Simulation of a complex mathematical operation.
    """
    time.sleep(2)
    total = 0
    for i in range(10 ** 7):
        total += i ** 2
    return total


def disk_io():
    """
    Simulation of intensive disk operations.
    """
    time.sleep(2)


def network_request():
    """
    Simulating waiting for a network request.
    """
    time.sleep(2)


heavy_computation()
disk_io()
network_request()
