import pytest
from unittest.mock import MagicMock

# This fixture is essential for testing any web application.
# It creates a test instance of your Flask app that can receive simulated requests.
@pytest.fixture(scope="module")
def app():
    """
    Creates and configures a new app instance for the test module.
    `scope="module"` means this will run only once per test file, which is efficient.
    """
    # We must import the app object from your main file.
    # To avoid circular dependencies, it's best to do it inside the fixture.
    from main import app as flask_app
    flask_app.config.update({"TESTING": True})
    yield flask_app

@pytest.fixture
def client(app):
    """
    Provides a test client for the Flask app. This client can make simulated
    HTTP requests (GET, POST, etc.) to your endpoints without needing a live server.
    """
    return app.test_client()

# The following fixtures are the cornerstone of testing an AI application.
# They replace real, slow, and expensive external services with controllable fakes.

@pytest.fixture
def mock_llm_model(mocker):
    """
    A powerful, reusable fixture that mocks the global `llm_model` instance.
    Any test that needs to control the LLM's behavior can now simply request this fixture.
    """
    # `mocker.patch` finds an object at a specified path and replaces it with a mock.
    # We must patch the object where it is *used*. Your code imports `llm_model` in
    # `analysis_service`, `llm_service`, and `main`. We must patch all of them.
    mock_instance = MagicMock()
    mocker.patch('app.services.analysis_service.llm_model', mock_instance)
    mocker.patch('app.services.llm_service.llm_model', mock_instance)
    mocker.patch('main.llm_model', mock_instance)
    return mock_instance

@pytest.fixture
def mock_embedding_model(mocker):
    """Mocks the global `embedding_model` instance used for vectorization."""
    mock_instance = MagicMock()
    mocker.patch('app.services.llm_service.embedding_model', mock_instance)
    mocker.patch('app.services.search_service.embedding_model', mock_instance)
    return mock_instance

@pytest.fixture
def mock_index_endpoint(mocker):
    """Mocks the Vertex AI Vector Search `index_endpoint` instance."""
    mock_instance = MagicMock()
    mocker.patch('app.services.search_service.index_endpoint', mock_instance)
    return mock_instance

@pytest.fixture
def mock_storage_client(mocker):
    """Mocks the Google Cloud Storage `storage_client` instance."""
    mock_instance = MagicMock()
    mocker.patch('app.services.document_service.storage_client', mock_instance)
    return mock_instance