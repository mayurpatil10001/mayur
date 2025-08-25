"""
Unit tests for feature importance analyzer.

Tests feature importance analysis, ranking, and selection functionality.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from sklearn.datasets import make_regression, make_classification

from trading_platform.services.machine_learning.feature_importance_analyzer import (
    FeatureImportanceAnalyzer, FeatureImportanceResult, FeatureAnalysisReport
)


class TestFeatureImportanceAnalyzer:
    """Test cases for FeatureImportanceAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create FeatureImportanceAnalyzer instance."""
        return FeatureImportanceAnalyzer(random_state=42, n_jobs=1)
    
    @pytest.fixture
    def regression_data(self):
        """Create sample regression data."""
        X, y = make_regression(
            n_samples=100,
            n_features=20,
            n_informative=10,
            noise=0.1,
            random_state=42
        )
        
        feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        features = pd.DataFrame(X, columns=feature_names)
        target = pd.Series(y, name='target')
        
        return features, target
    
    @pytest.fixture
    def classification_data(self):
        """Create sample classification data."""
        X, y = make_classification(
            n_samples=100,
            n_features=15,
            n_informative=8,
            n_redundant=2,
            n_clusters_per_class=1,
            random_state=42
        )
        
        feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        features = pd.DataFrame(X, columns=feature_names)
        target = pd.Series(y, name='target')
        
        return features, target
    
    def test_init(self):
        """Test FeatureImportanceAnalyzer initialization."""
        analyzer = FeatureImportanceAnalyzer(random_state=123, n_jobs=2)
        assert analyzer.random_state == 123
        assert analyzer.n_jobs == 2
    
    def test_analyze_feature_importance_regression(self, analyzer, regression_data):
        """Test feature importance analysis for regression."""
        features, target = regression_data
        
        report = analyzer.analyze_feature_importance(
            features, target, task_type='regression'
        )
        
        # Check report structure
        assert isinstance(report, FeatureAnalysisReport)
        assert report.total_features == len(features.columns)
        assert len(report.consensus_features) > 0
        assert 0 < report.selection_ratio <= 1
        
        # Check that methods were run
        assert len(report.method_results) > 0
        assert 'random_forest' in report.method_results
        
        # Check correlation analysis
        assert 'correlation_matrix' in report.correlation_analysis
        assert 'high_correlation_pairs' in report.correlation_analysis
    
    def test_analyze_feature_importance_classification(self, analyzer, classification_data):
        """Test feature importance analysis for classification."""
        features, target = classification_data
        
        report = analyzer.analyze_feature_importance(
            features, target, task_type='classification'
        )
        
        # Check report structure
        assert isinstance(report, FeatureAnalysisReport)
        assert report.total_features == len(features.columns)
        assert len(report.consensus_features) > 0
        
        # Check that classification-specific methods work
        assert len(report.method_results) > 0
    
    def test_random_forest_importance(self, analyzer, regression_data):
        """Test Random Forest importance calculation."""
        features, target = regression_data
        
        result = analyzer._random_forest_importance(features, target, 'regression')
        
        # Check result structure
        assert isinstance(result, FeatureImportanceResult)
        assert len(result.feature_names) == len(features.columns)
        assert len(result.importance_scores) == len(features.columns)
        assert result.importance_method == 'random_forest'
        
        # Check that scores are normalized
        assert max(result.importance_scores) <= 1.0
        assert min(result.importance_scores) >= 0.0
        
        # Check rankings
        assert len(result.feature_rankings) == len(features.columns)
        assert all(1 <= rank <= len(features.columns) for rank in result.feature_rankings.values())
    
    def test_permutation_importance(self, analyzer, regression_data):
        """Test permutation importance calculation."""
        features, target = regression_data
        
        result = analyzer._permutation_importance(features, target, 'regression')
        
        # Check result structure
        assert isinstance(result, FeatureImportanceResult)
        assert result.importance_method == 'permutation'
        assert len(result.importance_scores) == len(features.columns)
    
    def test_univariate_importance(self, analyzer, regression_data):
        """Test univariate statistical importance."""
        features, target = regression_data
        
        result = analyzer._univariate_importance(features, target, 'regression')
        
        # Check result structure
        assert isinstance(result, FeatureImportanceResult)
        assert result.importance_method == 'univariate'
        assert len(result.importance_scores) == len(features.columns)
    
    def test_mutual_info_importance(self, analyzer, regression_data):
        """Test mutual information importance."""
        features, target = regression_data
        
        result = analyzer._mutual_info_importance(features, target, 'regression')
        
        # Check result structure
        assert isinstance(result, FeatureImportanceResult)
        assert result.importance_method == 'mutual_info'
        assert len(result.importance_scores) == len(features.columns)
    
    def test_find_consensus_features(self, analyzer):
        """Test consensus feature finding."""
        # Create mock results
        result1 = Mock()
        result1.selected_features = ['feature_1', 'feature_2', 'feature_3']
        
        result2 = Mock()
        result2.selected_features = ['feature_1', 'feature_3', 'feature_4']
        
        result3 = Mock()
        result3.selected_features = ['feature_1', 'feature_5']
        
        method_results = {
            'method1': result1,
            'method2': result2,
            'method3': result3
        }
        
        consensus = analyzer._find_consensus_features(method_results)
        
        # feature_1 appears in all 3 methods, so should be first
        # feature_3 appears in 2 methods, so should be second
        assert 'feature_1' in consensus
        assert consensus[0] == 'feature_1'  # Most votes
    
    def test_analyze_correlations(self, analyzer, regression_data):
        """Test correlation analysis."""
        features, _ = regression_data
        
        # Add a highly correlated feature
        features['correlated_feature'] = features['feature_0'] * 0.95 + np.random.normal(0, 0.1, len(features))
        
        corr_analysis = analyzer._analyze_correlations(features)
        
        # Check analysis structure
        assert 'correlation_matrix' in corr_analysis
        assert 'high_correlation_pairs' in corr_analysis
        assert 'average_correlations' in corr_analysis
        assert 'most_correlated_features' in corr_analysis
        
        # Check correlation matrix
        assert corr_analysis['correlation_matrix'].shape == (len(features.columns), len(features.columns))
    
    def test_analyze_redundancy(self, analyzer, regression_data):
        """Test redundancy analysis."""
        features, _ = regression_data
        
        # Create mock method results
        mock_result = Mock()
        mock_result.selected_features = features.columns[:10].tolist()
        method_results = {'test_method': mock_result}
        
        redundancy_analysis = analyzer._analyze_redundancy(features, method_results)
        
        # Check analysis structure
        assert 'redundant_features' in redundancy_analysis
        assert 'feature_clusters' in redundancy_analysis
    
    def test_select_features_consensus(self, analyzer, regression_data):
        """Test consensus feature selection."""
        features, target = regression_data
        
        selected = analyzer.select_features(features, target, method='consensus')
        
        # Check that features are selected
        assert len(selected) > 0
        assert len(selected) <= len(features.columns)
        assert all(feature in features.columns for feature in selected)
    
    def test_select_features_single_method(self, analyzer, regression_data):
        """Test single method feature selection."""
        features, target = regression_data
        
        selected = analyzer.select_features(features, target, method='random_forest')
        
        # Check that features are selected
        assert len(selected) > 0
        assert all(feature in features.columns for feature in selected)
    
    def test_select_features_max_features(self, analyzer, regression_data):
        """Test feature selection with maximum limit."""
        features, target = regression_data
        
        selected = analyzer.select_features(
            features, target, method='random_forest', max_features=5
        )
        
        # Check that no more than max_features are selected
        assert len(selected) <= 5
    
    def test_create_importance_result(self, analyzer):
        """Test importance result creation."""
        feature_names = ['feature_1', 'feature_2', 'feature_3']
        importance_scores = np.array([0.5, 0.8, 0.2])
        
        result = analyzer._create_importance_result(
            feature_names, importance_scores, 'test_method'
        )
        
        # Check result structure
        assert isinstance(result, FeatureImportanceResult)
        assert result.feature_names == feature_names
        assert result.importance_method == 'test_method'
        assert len(result.importance_scores) == len(feature_names)
        
        # Check that scores are normalized
        assert max(result.importance_scores) == 1.0
        
        # Check rankings
        assert result.feature_rankings['feature_2'] == 1  # Highest score
        assert result.feature_rankings['feature_1'] == 2
        assert result.feature_rankings['feature_3'] == 3  # Lowest score
    
    def test_cluster_features_by_correlation(self, analyzer):
        """Test feature clustering by correlation."""
        # Create correlation matrix with known structure
        corr_data = np.array([
            [1.0, 0.8, 0.1, 0.2],
            [0.8, 1.0, 0.2, 0.1],
            [0.1, 0.2, 1.0, 0.9],
            [0.2, 0.1, 0.9, 1.0]
        ])
        
        corr_matrix = pd.DataFrame(
            corr_data,
            columns=['feature_1', 'feature_2', 'feature_3', 'feature_4'],
            index=['feature_1', 'feature_2', 'feature_3', 'feature_4']
        )
        
        clusters = analyzer._cluster_features_by_correlation(corr_matrix)
        
        # Should find two clusters: (feature_1, feature_2) and (feature_3, feature_4)
        assert len(clusters) == 2
        
        # Check cluster contents
        cluster_features = [set(cluster) for cluster in clusters]
        expected_clusters = [
            {'feature_1', 'feature_2'},
            {'feature_3', 'feature_4'}
        ]
        
        for expected in expected_clusters:
            assert expected in cluster_features
    
    def test_create_feature_importance_summary(self, analyzer, regression_data):
        """Test feature importance summary creation."""
        features, target = regression_data
        
        report = analyzer.analyze_feature_importance(features, target)
        summary = analyzer.create_feature_importance_summary(report)
        
        # Check summary structure
        assert 'total_features' in summary
        assert 'consensus_features' in summary
        assert 'selection_ratio' in summary
        assert 'methods_used' in summary
        assert 'top_consensus_features' in summary
        
        # Check values
        assert summary['total_features'] == len(features.columns)
        assert isinstance(summary['methods_used'], list)
        assert len(summary['top_consensus_features']) <= 10
    
    def test_empty_features_error(self, analyzer):
        """Test error handling with empty features."""
        empty_features = pd.DataFrame()
        target = pd.Series([1, 2, 3])
        
        with pytest.raises(ValueError, match="Features DataFrame cannot be empty"):
            analyzer.analyze_feature_importance(empty_features, target)
    
    def test_mismatched_length_error(self, analyzer):
        """Test error handling with mismatched feature and target lengths."""
        features = pd.DataFrame({'feature_1': [1, 2, 3]})
        target = pd.Series([1, 2])  # Different length
        
        with pytest.raises(ValueError, match="Features and target must have same length"):
            analyzer.analyze_feature_importance(features, target)
    
    def test_unknown_method_error(self, analyzer, regression_data):
        """Test error handling with unknown importance method."""
        features, target = regression_data
        
        with pytest.raises(ValueError, match="Unknown importance method"):
            analyzer._run_importance_method(features, target, 'unknown_method', 'regression')
    
    def test_method_failure_handling(self, analyzer, regression_data):
        """Test handling of method failures."""
        features, target = regression_data
        
        # Mock a method to fail
        with patch.object(analyzer, '_random_forest_importance', side_effect=Exception("Test error")):
            # Should still work with other methods
            report = analyzer.analyze_feature_importance(
                features, target, methods=['random_forest', 'univariate']
            )
            
            # Should have results from univariate method only
            assert 'univariate' in report.method_results
            assert 'random_forest' not in report.method_results
    
    def test_all_methods_fail(self, analyzer, regression_data):
        """Test error when all methods fail."""
        features, target = regression_data
        
        # Mock all methods to fail
        with patch.object(analyzer, '_run_importance_method', side_effect=Exception("Test error")):
            with pytest.raises(ValueError, match="No importance methods succeeded"):
                analyzer.analyze_feature_importance(features, target)
    
    @patch('matplotlib.pyplot.show')
    def test_plot_feature_importance(self, mock_show, analyzer, regression_data):
        """Test feature importance plotting."""
        features, target = regression_data
        
        result = analyzer._random_forest_importance(features, target, 'regression')
        
        # Should not raise an error
        analyzer.plot_feature_importance(result, top_n=10)
        
        # Check that plot was attempted to be shown
        mock_show.assert_called_once()
    
    def test_task_type_detection(self, analyzer, regression_data, classification_data):
        """Test automatic task type detection."""
        reg_features, reg_target = regression_data
        class_features, class_target = classification_data
        
        # Test regression detection
        selected_reg = analyzer.select_features(reg_features, reg_target, method='consensus')
        assert len(selected_reg) > 0
        
        # Test classification detection
        selected_class = analyzer.select_features(class_features, class_target, method='consensus')
        assert len(selected_class) > 0


if __name__ == '__main__':
    pytest.main([__file__])