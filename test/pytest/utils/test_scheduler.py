from src.utils.scheduler import Task

def test_task_initialization():
    def sample_function():
        return "Task executed"

    task = Task(
        name="Test Task",
        function=sample_function,
        interval=10,
        args=("arg1", "arg2"),
        kwargs={"key": "value"}
    )

    # Assertions
    assert task.name == "Test Task"
    assert task.function == sample_function
    assert task.interval == 10
    assert task.args == ("arg1", "arg2")
    assert task.kwargs == {"key": "value"}

def test_task_execution():
    result = []

    def sample_function(arg1, arg2, key=None):
        result.append((arg1, arg2, key))

    task = Task(
        name="Execution Task",
        function=sample_function,
        interval=5,
        args=("arg1", "arg2"),
        kwargs={"key": "value"}
    )

    # Simulate task execution
    task.function(*task.args, **task.kwargs)

    # Assertions
    assert result == [("arg1", "arg2", "value")]