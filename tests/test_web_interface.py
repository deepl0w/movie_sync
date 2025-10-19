"""
Tests for web interface API endpoints
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Import the classes we need
from web_interface import WebInterface
from queue_manager import QueueManager
from config import Config


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory"""
    data_dir = tmp_path / "test_movie_sync"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_movies():
    """Sample movie data for testing"""
    return {
        'pending': [
            {
                'id': '1001',
                'title': 'Test Movie 1',
                'year': '2020',
                'director': 'Test Director 1',
                'status': 'pending',
                'added_at': 1234567890
            },
            {
                'id': '1002',
                'title': 'Test Movie 2',
                'year': '2021',
                'director': 'Test Director 2',
                'status': 'pending',
                'added_at': 1234567891,
                'skipped': True
            }
        ],
        'failed': [
            {
                'id': '2001',
                'title': 'Failed Movie',
                'year': '2019',
                'status': 'failed',
                'retry_count': 2,
                'last_error': 'Connection timeout',
                'retry_after': 1234567900
            }
        ],
        'completed': [
            {
                'id': '3001',
                'title': 'Completed Movie 1',
                'year': '2018',
                'status': 'completed',
                'completed_at': 1234567800
            },
            {
                'id': '3002',
                'title': 'Completed Movie 2',
                'year': '2017',
                'status': 'completed',
                'completed_at': 1234567700
            }
        ],
        'removed': [
            {
                'id': '4001',
                'title': 'Removed Movie',
                'year': '2016',
                'status': 'removed',
                'removed_at': 1234567600,
                'completed_at': 1234567500
            }
        ]
    }


@pytest.fixture
def queue_manager(temp_data_dir, sample_movies):
    """Create a QueueManager instance with test data"""
    # Create QueueManager first (creates empty files)
    qm = QueueManager(str(temp_data_dir))
    
    # Load sample data into queues
    qm.pending_queue = sample_movies['pending'].copy()
    qm.failed_queue = sample_movies['failed'].copy()
    qm.completed_queue = sample_movies['completed'].copy()
    qm.removed_queue = sample_movies['removed'].copy()
    
    # Save to files
    qm._save_json(qm.pending_file, qm.pending_queue)
    qm._save_json(qm.failed_file, qm.failed_queue)
    qm._save_json(qm.completed_file, qm.completed_queue)
    qm._save_json(qm.removed_file, qm.removed_queue)
    
    return qm


@pytest.fixture
def cleanup_service_mock():
    """Mock cleanup service"""
    mock = Mock()
    mock.cleanup_movie = Mock(return_value={
        'files_deleted': 2,
        'torrent_deleted': True,
        'qbt_removed': True,
        'errors': []
    })
    return mock


@pytest.fixture
def web_interface(queue_manager, cleanup_service_mock):
    """Create WebInterface instance for testing"""
    web = WebInterface(
        queue_manager=queue_manager,
        port=5001,  # Use different port for testing
        cleanup_service=cleanup_service_mock
    )
    web.app.config['TESTING'] = True
    return web


@pytest.fixture
def client(web_interface):
    """Create Flask test client"""
    return web_interface.app.test_client()


class TestQueueEndpoints:
    """Test queue retrieval endpoints"""
    
    def test_get_stats(self, client, sample_movies):
        """Test /api/stats endpoint"""
        response = client.get('/api/stats')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['pending'] == len(sample_movies['pending'])
        assert data['failed'] == len(sample_movies['failed'])
        assert data['completed'] == len(sample_movies['completed'])
        assert data['removed'] == len(sample_movies['removed'])
        assert data['permanent_failures'] == 0
    
    def test_get_pending_queue(self, client, sample_movies):
        """Test /api/queue/pending endpoint"""
        response = client.get('/api/queue/pending')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == len(sample_movies['pending'])
        assert data[0]['id'] == '1001'
        assert data[1]['skipped'] == True
    
    def test_get_failed_queue(self, client, sample_movies):
        """Test /api/queue/failed endpoint"""
        response = client.get('/api/queue/failed')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == len(sample_movies['failed'])
        assert data[0]['id'] == '2001'
        assert data[0]['retry_count'] == 2
    
    def test_get_completed_queue(self, client, sample_movies):
        """Test /api/queue/completed endpoint"""
        response = client.get('/api/queue/completed')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == len(sample_movies['completed'])
    
    def test_get_removed_queue(self, client, sample_movies):
        """Test /api/queue/removed endpoint"""
        response = client.get('/api/queue/removed')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == len(sample_movies['removed'])
        assert data[0]['status'] == 'removed'
    
    def test_get_invalid_queue(self, client):
        """Test invalid queue name"""
        response = client.get('/api/queue/invalid')
        assert response.status_code == 400


class TestMoveMovieEndpoint:
    """Test movie movement between queues"""
    
    def test_move_pending_to_failed(self, client, queue_manager):
        """Test moving movie from pending to failed"""
        response = client.post(
            '/api/movie/1001/move',
            data=json.dumps({'target_queue': 'failed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie moved
        assert len(queue_manager.pending_queue) == 1
        assert len(queue_manager.failed_queue) == 2
        assert any(m['id'] == '1001' for m in queue_manager.failed_queue)
    
    def test_move_completed_to_removed(self, client, queue_manager):
        """Test moving movie from completed to removed (Mark for Removal button)"""
        response = client.post(
            '/api/movie/3001/move',
            data=json.dumps({'target_queue': 'removed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie moved
        assert len(queue_manager.completed_queue) == 1
        assert len(queue_manager.removed_queue) == 2
        
        # Verify it has removed status
        moved_movie = next(m for m in queue_manager.removed_queue if m['id'] == '3001')
        assert moved_movie['status'] == 'removed'
        assert 'removed_at' in moved_movie
    
    def test_move_removed_to_completed(self, client, queue_manager):
        """Test moving movie from removed to completed (To Completed button)"""
        response = client.post(
            '/api/movie/4001/move',
            data=json.dumps({'target_queue': 'completed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie moved
        assert len(queue_manager.removed_queue) == 0
        assert len(queue_manager.completed_queue) == 3
        
        # Verify removed_at was cleaned up
        moved_movie = next(m for m in queue_manager.completed_queue if m['id'] == '4001')
        assert moved_movie['status'] == 'completed'
        assert 'removed_at' not in moved_movie
        assert 'completed_at' in moved_movie
    
    def test_move_failed_to_pending(self, client, queue_manager):
        """Test moving movie from failed to pending (Reset Retry button)"""
        response = client.post(
            '/api/movie/2001/move',
            data=json.dumps({'target_queue': 'pending'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie moved
        assert len(queue_manager.failed_queue) == 0
        assert len(queue_manager.pending_queue) == 3
    
    def test_move_invalid_target_queue(self, client):
        """Test moving to invalid queue"""
        response = client.post(
            '/api/movie/1001/move',
            data=json.dumps({'target_queue': 'invalid'}),
            content_type='application/json'
        )
        assert response.status_code == 400
    
    def test_move_nonexistent_movie(self, client):
        """Test moving movie that doesn't exist"""
        response = client.post(
            '/api/movie/99999/move',
            data=json.dumps({'target_queue': 'completed'}),
            content_type='application/json'
        )
        assert response.status_code == 404


class TestSkipUnskipEndpoints:
    """Test skip/unskip functionality"""
    
    def test_skip_movie(self, client, queue_manager):
        """Test skipping a movie (Skip button)"""
        response = client.post('/api/movie/1001/skip')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie is skipped
        movie = next(m for m in queue_manager.pending_queue if m['id'] == '1001')
        assert movie['skipped'] == True
    
    def test_unskip_movie(self, client, queue_manager):
        """Test unskipping a movie (Unskip button)"""
        # Movie 1002 is already skipped
        response = client.post('/api/movie/1002/unskip')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie is unskipped
        movie = next(m for m in queue_manager.pending_queue if m['id'] == '1002')
        assert movie['skipped'] == False
    
    def test_skip_nonexistent_movie(self, client):
        """Test skipping movie that doesn't exist"""
        response = client.post('/api/movie/99999/skip')
        assert response.status_code == 404
    
    def test_unskip_nonexistent_movie(self, client):
        """Test unskipping movie that doesn't exist"""
        response = client.post('/api/movie/99999/unskip')
        assert response.status_code == 404


class TestForceDownloadEndpoint:
    """Test force download functionality"""
    
    def test_force_download(self, client, queue_manager):
        """Test force download (Force Download button)"""
        response = client.post('/api/movie/1001/force-download')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify force_download flag is set
        movie = next(m for m in queue_manager.pending_queue if m['id'] == '1001')
        assert movie.get('force_download') == True
    
    def test_force_download_nonexistent_movie(self, client):
        """Test force download on nonexistent movie"""
        response = client.post('/api/movie/99999/force-download')
        assert response.status_code == 404
    
    def test_force_download_from_failed_space_limit(self, client, queue_manager):
        """Test force download from failed queue for space limit failures"""
        # Add a movie to failed queue with space limit reason
        space_limit_movie = {
            'id': '5001',
            'title': 'Space Limited Movie',
            'year': 2023,
            'failed_reason': 'space_limit',
            'last_error': 'Download space limit reached',
            'retry_count': 0
        }
        queue_manager.failed_queue.append(space_limit_movie)
        queue_manager._save_json(queue_manager.failed_file, queue_manager.failed_queue)
        
        # Force download should move it to pending
        response = client.post('/api/movie/5001/force-download')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie is now in pending queue
        assert any(m['id'] == '5001' for m in queue_manager.pending_queue)
        # Verify movie is removed from failed queue
        assert not any(m['id'] == '5001' for m in queue_manager.failed_queue)
        
        # Verify force_download flag is set and failed metadata removed
        movie = next(m for m in queue_manager.pending_queue if m['id'] == '5001')
        assert movie.get('force_download') == True
        assert 'failed_reason' not in movie
        assert 'last_error' not in movie
        assert 'retry_count' not in movie
    
    def test_force_download_from_failed_non_space_limit(self, client, queue_manager):
        """Test force download from failed queue for non-space limit failures (should fail)"""
        # Add a movie to failed queue with regular failure
        regular_failed_movie = {
            'id': '5002',
            'title': 'Regular Failed Movie',
            'year': 2023,
            'last_error': 'Download failed',
            'retry_count': 3
        }
        queue_manager.failed_queue.append(regular_failed_movie)
        queue_manager._save_json(queue_manager.failed_file, queue_manager.failed_queue)
        
        # Force download should fail for non-space limit failures
        response = client.post('/api/movie/5002/force-download')
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert 'error' in data
        assert 'space limit' in data['error'].lower()


class TestForceDeleteEndpoint:
    """Test force delete functionality"""
    
    def test_force_delete(self, client, queue_manager, cleanup_service_mock):
        """Test force delete (Force Delete Now button)"""
        response = client.post('/api/movie/4001/force-delete')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'files' in data['message'].lower() or 'torrent' in data['message'].lower()
        
        # Verify cleanup was called
        cleanup_service_mock.cleanup_movie.assert_called_once()
        
        # Verify movie was removed from queue
        assert len(queue_manager.removed_queue) == 0
    
    def test_force_delete_nonexistent_movie(self, client):
        """Test force delete on nonexistent movie"""
        response = client.post('/api/movie/99999/force-delete')
        assert response.status_code == 404
    
    def test_force_delete_without_cleanup_service(self, queue_manager):
        """Test force delete when cleanup service is not available"""
        web = WebInterface(
            queue_manager=queue_manager,
            port=5002,
            cleanup_service=None  # No cleanup service
        )
        web.app.config['TESTING'] = True
        client = web.app.test_client()
        
        response = client.post('/api/movie/4001/force-delete')
        assert response.status_code == 500
        assert 'not available' in response.get_json()['error'].lower()


class TestDeleteEndpoint:
    """Test movie deletion from all queues"""
    
    def test_delete_movie(self, client, queue_manager):
        """Test deleting movie from all queues"""
        # First add a movie to multiple queues
        test_movie = {
            'id': '5001',
            'title': 'Test Delete Movie',
            'status': 'pending'
        }
        queue_manager.pending_queue.append(test_movie.copy())
        queue_manager.completed_queue.append(test_movie.copy())
        queue_manager._save_json(queue_manager.pending_file, queue_manager.pending_queue)
        queue_manager._save_json(queue_manager.completed_file, queue_manager.completed_queue)
        
        response = client.post('/api/movie/5001/delete')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify movie removed from pending queue (delete only removes from one queue)
        assert not any(m['id'] == '5001' for m in queue_manager.pending_queue)
    
    def test_delete_nonexistent_movie(self, client):
        """Test deleting movie that doesn't exist"""
        response = client.post('/api/movie/99999/delete')
        assert response.status_code == 404


class TestReorderEndpoint:
    """Test queue reordering (drag and drop)"""
    
    def test_reorder_pending_queue(self, client, queue_manager):
        """Test reordering pending queue"""
        # Get initial order
        initial_order = [m['id'] for m in queue_manager.pending_queue]
        assert len(initial_order) == 2
        
        # Drag second movie (1002) to first position (drag it onto 1001)
        response = client.post(
            '/api/queue/reorder',
            data=json.dumps({
                'queue': 'pending',
                'dragged_id': '1002',
                'target_id': '1001'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        
        # Verify order changed (1002 should now be first)
        current_order = [m['id'] for m in queue_manager.pending_queue]
        assert current_order[0] == '1002'
        assert current_order[1] == '1001'
    
    def test_reorder_with_missing_movies(self, client):
        """Test reordering with missing movie IDs"""
        response = client.post(
            '/api/queue/reorder',
            data=json.dumps({
                'queue': 'pending',
                'dragged_id': '99999',
                'target_id': '1001'
            }),
            content_type='application/json'
        )
        assert response.status_code == 404
    
    def test_reorder_invalid_queue(self, client):
        """Test reordering invalid queue"""
        response = client.post(
            '/api/queue/reorder',
            data=json.dumps({'queue': 'invalid', 'order': ['1001']}),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestConfigEndpoints:
    """Test configuration endpoints"""
    
    def test_get_config(self, client):
        """Test getting configuration"""
        response = client.get('/api/config')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, dict)
    
    @patch('config.Config.save')
    def test_save_config(self, mock_save, client):
        """Test saving configuration"""
        new_config = {
            'letterboxd_username': 'testuser',
            'check_interval': 3600
        }
        
        response = client.post(
            '/api/config',
            data=json.dumps(new_config),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True


class TestRootEndpoint:
    """Test root endpoint (HTML page)"""
    
    def test_get_index_page(self, client):
        """Test that index page loads"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Movie Sync Dashboard' in response.data or b'html' in response.data


class TestButtonScenarios:
    """Test complete button click scenarios"""
    
    def test_skip_button_workflow(self, client, queue_manager):
        """Test complete Skip button workflow"""
        # 1. Get initial pending queue
        response = client.get('/api/queue/pending')
        initial_data = json.loads(response.data)
        movie = initial_data[0]
        assert movie.get('skipped') != True
        
        # 2. Click Skip button
        response = client.post(f'/api/movie/{movie["id"]}/skip')
        assert response.status_code == 200
        
        # 3. Verify movie is now skipped
        response = client.get('/api/queue/pending')
        updated_data = json.loads(response.data)
        updated_movie = next(m for m in updated_data if m['id'] == movie['id'])
        assert updated_movie['skipped'] == True
    
    def test_mark_for_removal_workflow(self, client, queue_manager):
        """Test complete Mark for Removal button workflow"""
        # 1. Get completed movie
        response = client.get('/api/queue/completed')
        completed_movies = json.loads(response.data)
        movie_id = completed_movies[0]['id']
        
        # 2. Click Mark for Removal button
        response = client.post(
            f'/api/movie/{movie_id}/move',
            data=json.dumps({'target_queue': 'removed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        # 3. Verify movie in removed queue
        response = client.get('/api/queue/removed')
        removed_movies = json.loads(response.data)
        assert any(m['id'] == movie_id for m in removed_movies)
        
        # 4. Verify movie not in completed queue
        response = client.get('/api/queue/completed')
        completed_movies = json.loads(response.data)
        assert not any(m['id'] == movie_id for m in completed_movies)
    
    def test_to_completed_button_workflow(self, client, queue_manager):
        """Test complete To Completed button workflow"""
        # 1. Get removed movie
        response = client.get('/api/queue/removed')
        removed_movies = json.loads(response.data)
        movie_id = removed_movies[0]['id']
        
        # 2. Click To Completed button
        response = client.post(
            f'/api/movie/{movie_id}/move',
            data=json.dumps({'target_queue': 'completed'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        # 3. Verify movie in completed queue
        response = client.get('/api/queue/completed')
        completed_movies = json.loads(response.data)
        assert any(m['id'] == movie_id for m in completed_movies)
        
        # 4. Verify movie not in removed queue
        response = client.get('/api/queue/removed')
        removed_movies = json.loads(response.data)
        assert not any(m['id'] == movie_id for m in removed_movies)
        
        # 5. Verify removed_at was cleaned up
        moved_movie = next(m for m in completed_movies if m['id'] == movie_id)
        assert 'removed_at' not in moved_movie
    
    def test_force_download_button_workflow(self, client, queue_manager):
        """Test complete Force Download button workflow"""
        # 1. Get pending movie
        response = client.get('/api/queue/pending')
        pending_movies = json.loads(response.data)
        movie_id = pending_movies[0]['id']
        
        # 2. Click Force Download button
        response = client.post(f'/api/movie/{movie_id}/force-download')
        assert response.status_code == 200
        
        # 3. Verify force_download flag is set
        response = client.get('/api/queue/pending')
        pending_movies = json.loads(response.data)
        movie = next(m for m in pending_movies if m['id'] == movie_id)
        assert movie.get('force_download') == True
    
    def test_force_delete_button_workflow(self, client, queue_manager, cleanup_service_mock):
        """Test complete Force Delete Now button workflow"""
        # 1. Get removed movie
        response = client.get('/api/queue/removed')
        removed_movies = json.loads(response.data)
        movie_id = removed_movies[0]['id']
        initial_count = len(removed_movies)
        
        # 2. Click Force Delete Now button
        response = client.post(f'/api/movie/{movie_id}/force-delete')
        assert response.status_code == 200
        
        # 3. Verify cleanup was called
        cleanup_service_mock.cleanup_movie.assert_called()
        
        # 4. Verify movie removed from queue
        response = client.get('/api/queue/removed')
        removed_movies = json.loads(response.data)
        assert len(removed_movies) == initial_count - 1
        assert not any(m['id'] == movie_id for m in removed_movies)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
