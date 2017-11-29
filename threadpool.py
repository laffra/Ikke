from queue import Queue
from threading import Thread
import traceback

class Worker(Thread):
    """ Thread executing tasks from a given tasks queue """
    def __init__(self, tasks):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            func, args = self.tasks.get()
            try:
                func(*args)
            except Exception as e:
                # An exception happened in this thread
                traceback.print_exc()
            finally:
                # Mark this task as done, whether an exception happened or not
                self.tasks.task_done()


class ThreadPool:
    """ Pool of threads consuming tasks from a queue """
    def __init__(self, task_count:int, tasks=None):
        self.tasks = Queue(task_count)
        for _ in range(task_count):
            Worker(self.tasks)
        if tasks:
            for task in tasks:
                self.add_task(*task)

    def add_task(self, func, *args):
        self.tasks.put((func, args))

    def wait_completion(self):
        """ Wait for completion of all the tasks in the queue """
        self.tasks.join()


if __name__ == "__main__":
    from time import sleep
    import time

    start = time.time()

    def wait_delay(d):
        print("sleeping for (%d)sec" % d)
        sleep(d)

    pool = ThreadPool(15)
    pool.add_task(wait_delay, 1)
    pool.add_task(wait_delay, 3)
    pool.add_task(wait_delay, 2)
    pool.add_task(wait_delay, 5)
    pool.wait_completion()

    print('The 4 tasks took %.1fs, not 11s' % (time.time() - start))
