import threading
import queue
import traceback

class HardwareIO:
    '''
    Single-threaded hardware executor.
    ALL hardware calls must go through this.
    '''

    def __init__(self):
        self.q = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def call(self, fn, *args, **kwargs):
        '''
        Synchronous hardware call.
        '''
        result_q = queue.Queue()
        self.q.put((fn, args, kwargs, result_q))
        return result_q.get()

    def _run(self):
        while True:
            fn, args, kwargs, result_q = self.q.get()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                traceback.print_exc()
                result = None
            result_q.put(result)

