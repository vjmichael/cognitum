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


# Optional same-context batching of TRUSTED, effect-free and deterministic
# plugin invocations. The parent Runtime must validate EVERY invocation first.
# This is not an OS sandbox: child inherits user-level process privileges.
MAX_BATCH = 16


def _run_batch(connection, factory, calls):
    """No partial IPC: if any plugin fails, discard the whole batch."""
    try:
        if type(calls) is not list or not 1 <= len(calls) <= MAX_BATCH:
            raise ValueError('invalid batch')
        results = []
        for operation, payload in calls:
            # New trusted implementation per request to prevent mutable plugin
            # state from leaking between entries of one worker batch.
            results.append(factory().handle(operation, payload))
        connection.send(('ok', results))
    except ValueError:
        connection.send(('invalid_input', None))
    except BaseException:
        connection.send(('error', None))
    finally:
        connection.close()


def execute_batch(factory, calls, timeout_ms):
    """One disposable spawn, one bounded batch, one aggregate deadline.

    Only call after host-only effect/replay/identity checks. Existing `execute`
    deliberately remains unchanged for all normal and effectful operations.
    """
    if type(calls) not in (list, tuple) or not 1 <= len(calls) <= MAX_BATCH:
        raise ValueError('invalid batch size')
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 10000:
        raise ValueError('invalid batch deadline')
    ctx = mp.get_context('spawn')
    reader, writer = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_run_batch,
                          args=(writer, factory, list(calls)), daemon=True)
    try:
        process.start()
        writer.close()
        if not reader.poll(timeout_ms / 1000):
            return 'timed_out', None
        try:
            status, result = reader.recv()
            if status == 'ok' and (type(result) is not list or len(result) != len(calls)):
                return 'error', None
            return status, result
        except (EOFError, ValueError, TypeError):
            return 'error', None
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
