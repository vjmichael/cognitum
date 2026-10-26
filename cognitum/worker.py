"""Disposable trusted-code workers: timeout containment, NOT an OS sandbox."""
import multiprocessing as mp

def _run(connection, factory, operation, payload):
    try:
        result = factory().handle(operation, payload)
        connection.send(("ok", result))
    except ValueError:
        connection.send(("invalid_input", None))
    except BaseException:
        connection.send(("error", None))
    finally:
        connection.close()

def execute(factory, operation, payload, timeout_ms):
    context = mp.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_run, args=(writer, factory, operation, payload), daemon=True)
    try:
        process.start()
        writer.close()
        if not reader.poll(timeout_ms / 1000):
            return "timed_out", None
        try:
            return reader.recv()
        except EOFError:
            return "error", None
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        reader.close()
        writer.close()
