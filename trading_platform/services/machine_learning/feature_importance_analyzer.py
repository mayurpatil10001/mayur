"""
Feature importance analysis for machine learning models.

This service analyzes feature importance to identify the most predictive variables
for trading optimization models.

Requirements: 4.1, 4.4
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_regression, f_classif, mutual_info_regression, mutual_info_classif
from sklearn.inspection import permutation_importance
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns


@dataclass
class FeatureImportanceResult:
    """Results from feature importance analysis."""
    feature_names: List[str]
    importance_scores: List[float]
    importance_method: str
    feature_rankings: Dict[str, int]
    top_features: List[str]
    bottom_features: List[str]
    importance_threshold: float
    selected_features: List[str]


@dataclass
class FeatureAnalysisReport:
    """Comprehensive feature analysis report."""
    total_features: int
    selected_features: int
    selection_ratio: float
    importance_methods: List[str]
    consensus_features: List[str]
    method_results: Dict[str, FeatureImportanceResult]
    correlation_analysis: Dict[str, Any]
    redundancy_analysis: Dict[str, Any]


class FeatureImportanceAnalyzer:
    """
    Analyzes feature importance using multiple methods.
    
    Provides comprehensive analysis of which features are most predictive
    for trading optimization models.
    """
    
    def __init__(self, 
                 random_state: int = 42,
                 n_jobs: int = -1):
        """
        Initialize the feature importance analyzer.
        
        Args:
            random_state: Random state for reproducibility
            n_jobs: Number of parallel jobs for computation
        """
        self.random_state = random_state
        self.n_jobs = n_jobs
        
    def analyze_feature_importance(self,
                                 features: pd.DataFrame,
                                 target: pd.Series,
                                 task_type: str = 'regression',
                                 methods: List[str] = None) -> FeatureAnalysisReport:
        """
        Perform comprehensive feature importance analysis.
        
        Args:
            features: Feature matrix
            target: Target variable
            task_type: 'regression' or 'classification'
            methods: List of methods to use for importance analysis
            
        Returns:
            FeatureAnalysisReport with comprehensive analysis
        """
        if methods is None:
            methods = ['random_forest', 'permutation', 'univariate', 'mutual_info']
        
        # Validate inputs
        if features.empty:
            raise ValueError("Features DataFrame cannot be empty")
        if len(target) != len(features):
            raise ValueError("Features and target must have same length")
        
        method_results = {}
        
        # Run each importance method
        for method in methods:
            try:
                result = self._run_importance_method(features, target, method, task_type)
                method_results[method] = result
            except Exception as e:
                print(f"Warning: Failed to run {method} importance analysis: {e}")
                continue
        
        if not method_results:
            raise ValueError("No importance methods succeeded")
        
        # Find consensus features
        consensus_features = self._find_consensus_features(method_results)
        
        # Analyze correlations
        correlation_analysis = self._analyze_correlations(features)
        
        # Analyze redundancy
        redundancy_analysis = self._analyze_redundancy(features, method_results)
        
        return FeatureAnalysisReport(
            total_features=len(features.columns),
            selected_features=len(consensus_features),
            selection_ratio=len(consensus_features) / len(features.columns),
            importance_methods=list(method_results.keys()),
            consensus_features=consensus_features,
            method_results=method_results,
            correlation_analysis=correlation_analysis,
            redundancy_analysis=redundancy_analysis
        )
    
    def _run_importance_method(self,
                              features: pd.DataFrame,
                              target: pd.Series,
                              method: str,
                              task_type: str) -> FeatureImportanceResult:
        """Run a specific importance analysis method."""
        
        if method == 'random_forest':
            return self._random_forest_importance(features, target, task_type)
        elif method == 'permutation':
            return self._permutation_importance(features, target, task_type)
        elif method == 'univariate':
            return self._univariate_importance(features, target, task_type)
        elif method == 'mutual_info':
            return self._mutual_info_importance(features, target, task_type)
        else:
            raise ValueError(f"Unknown importance method: {method}")
    
    def _random_forest_importance(self,
                                 features: pd.DataFrame,
                                 target: pd.Series,
                                 task_type: str) -> FeatureImportanceResult:
        """Calculate feature importance using Random Forest."""
        
        if task_type == 'regression':
            model = RandomForestRegressor(
                n_estimators=100,
                random_state=self.random_state,
                n_jobs=self.n_jobs
            )
        else:
            model = RandomForestClassifier(
                n_estimators=100,
                random_state=self.random_state,
                n_jobs=self.n_jobs
            )
        
        # Fit model
        model.fit(features, target)
        
        # Get importance scores
        importance_scores = model.feature_importances_
        
        return self._create_importance_result(
            features.columns.tolist(),
            importance_scores,
            'random_forest'
        )
    
    def _permutation_importance(self,
                               features: pd.DataFrame,
                               target: pd.Series,
                               task_type: str) -> FeatureImportanceResult:
        """Calculate feature importance using permutation importance."""
        
        # Use a simple model for permutation importance
        if task_type == 'regression':
            model = RandomForestRegressor(
                n_estimators=50,  # Fewer trees for speed
                random_state=self.random_state,
                n_jobs=self.n_jobs
            )
        else:
            model = RandomForestClassifier(
                n_estimators=50,
                random_state=self.random_state,
                n_jobs=self.n_jobs
            )
        
        # Fit model
        model.fit(features, target)
        
        # Calculate permutation importance
        perm_importance = permutation_importance(
            model, features, target,
            n_repeats=10,
            random_state=self.random_state,
            n_jobs=self.n_jobs
        )
        
        return self._create_importance_result(
            features.columns.tolist(),
            perm_importance.importances_mean,
            'permutation'
        )
    
    def _univariate_importance(self,
                              features: pd.DataFrame,
                              target: pd.Series,
                              task_type: str) -> FeatureImportanceResult:
        """Calculate feature importance using univariate statistical tests."""
        
        if task_type == 'regression':
            score_func = f_regression
        else:
            score_func = f_classif
        
        # Calculate F-scores
        selector = SelectKBest(score_func=score_func, k='all')
        selector.fit(features, target)
        
        # Get scores (higher is better)
        scores = selector.scores_
        
        return self._create_importance_result(
            features.columns.tolist(),
            scores,
            'univariate'
        )
    
    def _mutual_info_importance(self,
                               features: pd.DataFrame,
                               target: pd.Series,
                               task_type: str) -> FeatureImportanceResult:
        """Calculate feature importance using mutual information."""
        
        if task_type == 'regression':
            mi_scores = mutual_info_regression(
                features, target,
                random_state=self.random_state
            )
        else:
            mi_scores = mutual_info_classif(
                features, target,
                random_state=self.random_state
            )
        
        return self._create_importance_result(
            features.columns.tolist(),
            mi_scores,
            'mutual_info'
        )
    
    def _create_importance_result(self,
                                 feature_names: List[str],
                                 importance_scores: np.ndarray,
                                 method: str) -> FeatureImportanceResult:
        """Create a standardized importance result."""
        
        # Normalize scores to 0-1 range
        if np.max(importance_scores) > 0:
            normalized_scores = importance_scores / np.max(importance_scores)
        else:
            normalized_scores = importance_scores
        
        # Create rankings
        rankings = {}
        sorted_indices = np.argsort(normalized_scores)[::-1]
        for rank, idx in enumerate(sorted_indices):
            rankings[feature_names[idx]] = rank + 1
        
        # Determine threshold (top 50% or features with score > 0.1)
        threshold = max(0.1, np.percentile(normalized_scores, 50))
        
        # Select features above threshold
        selected_features = [
            feature_names[i] for i, score in enumerate(normalized_scores)
            if score >= threshold
        ]
        
        # Get top and bottom features
        top_features = [feature_names[i] for i in sorted_indices[:10]]
        bottom_features = [feature_names[i] for i in sorted_indices[-10:]]
        
        return FeatureImportanceResult(
            feature_names=feature_names,
            importance_scores=normalized_scores.tolist(),
            importance_method=method,
            feature_rankings=rankings,
            top_features=top_features,
            bottom_features=bottom_features,
            importance_threshold=threshold,
            selected_features=selected_features
        )
    
    def _find_consensus_features(self,
                                method_results: Dict[str, FeatureImportanceResult]) -> List[str]:
        """Find features that are consistently important across methods."""
        
        if not method_results:
            return []
        
        # Count how many methods select each feature
        feature_votes = {}
        for method, result in method_results.items():
            for feature in result.selected_features:
                feature_votes[feature] = feature_votes.get(feature, 0) + 1
        
        # Require feature to be selected by at least half of the methods
        min_votes = max(1, len(method_results) // 2)
        consensus_features = [
            feature for feature, votes in feature_votes.items()
            if votes >= min_votes
        ]
        
        # Sort by total votes
        consensus_features.sort(key=lambda f: feature_votes[f], reverse=True)
        
        return consensus_features
    
    def _analyze_correlations(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Analyze feature correlations."""
        
        # Calculate correlation matrix
        corr_matrix = features.corr()
        
        # Find highly correlated feature pairs
        high_corr_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                corr_value = corr_matrix.iloc[i, j]
                if abs(corr_value) > 0.8:  # High correlation threshold
                    high_corr_pairs.append({
                        'feature1': corr_matrix.columns[i],
                        'feature2': corr_matrix.columns[j],
                        'correlation': corr_value
                    })
        
        # Calculate average absolute correlation for each feature
        avg_correlations = {}
        for feature in corr_matrix.columns:
            other_corrs = corr_matrix[feature].drop(feature)
            avg_correlations[feature] = np.mean(np.abs(other_corrs))
        
        return {
            'correlation_matrix': corr_matrix,
            'high_correlation_pairs': high_corr_pairs,
            'average_correlations': avg_correlations,
            'most_correlated_features': sorted(
                avg_correlations.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def _analyze_redundancy(self,
                           features: pd.DataFrame,
                           method_results: Dict[str, FeatureImportanceResult]) -> Dict[str, Any]:
        """Analyze feature redundancy."""
        
        # Get all selected features across methods
        all_selected = set()
        for result in method_results.values():
            all_selected.update(result.selected_features)
        
        if not all_selected:
            return {'redundant_features': [], 'feature_clusters': []}
        
        # Calculate correlation matrix for selected features only
        selected_features_df = features[list(all_selected)]
        corr_matrix = selected_features_df.corr()
        
        # Find redundant features (highly correlated with others)
        redundant_features = []
        for feature in corr_matrix.columns:
            other_corrs = corr_matrix[feature].drop(feature)
            max_corr = np.max(np.abs(other_corrs))
            if max_corr > 0.9:  # Very high correlation threshold
                redundant_features.append({
                    'feature': feature,
                    'max_correlation': max_corr,
                    'correlated_with': other_corrs.idxmax()
                })
        
        # Simple clustering based on correlation
        feature_clusters = self._cluster_features_by_correlation(corr_matrix)
        
        return {
            'redundant_features': redundant_features,
            'feature_clusters': feature_clusters
        }
    
    def _cluster_features_by_correlation(self, corr_matrix: pd.DataFrame) -> List[List[str]]:
        """Cluster features based on correlation."""
        
        # Simple clustering: group features with correlation > 0.7
        clusters = []
        used_features = set()
        
        for feature in corr_matrix.columns:
            if feature in used_features:
                continue
            
            # Find all features highly correlated with this one
            cluster = [feature]
            for other_feature in corr_matrix.columns:
                if (other_feature != feature and 
                    other_feature not in used_features and
                    abs(corr_matrix.loc[feature, other_feature]) > 0.7):
                    cluster.append(other_feature)
            
            if len(cluster) > 1:
                clusters.append(cluster)
                used_features.update(cluster)
        
        return clusters
    
    def select_features(self,
                       features: pd.DataFrame,
                       target: pd.Series,
                       method: str = 'consensus',
                       max_features: Optional[int] = None) -> List[str]:
        """
        Select the most important features.
        
        Args:
            features: Feature matrix
            target: Target variable
            method: Selection method ('consensus', 'random_forest', etc.)
            max_features: Maximum number of features to select
            
        Returns:
            List of selected feature names
        """
        
        if method == 'consensus':
            # Run full analysis and return consensus features
            task_type = 'regression' if target.dtype in ['float64', 'float32'] else 'classification'
            analysis = self.analyze_feature_importance(features, target, task_type)
            selected = analysis.consensus_features
        else:
            # Run single method
            task_type = 'regression' if target.dtype in ['float64', 'float32'] else 'classification'
            result = self._run_importance_method(features, target, method, task_type)
            selected = result.selected_features
        
        # Limit number of features if specified
        if max_features and len(selected) > max_features:
            selected = selected[:max_features]
        
        return selected
    
    def plot_feature_importance(self,
                               importance_result: FeatureImportanceResult,
                               top_n: int = 20,
                               figsize: Tuple[int, int] = (12, 8)) -> None:
        """
        Plot feature importance scores.
        
        Args:
            importance_result: Result from importance analysis
            top_n: Number of top features to plot
            figsize: Figure size
        """
        
        # Get top N features
        feature_scores = list(zip(importance_result.feature_names, importance_result.importance_scores))
        feature_scores.sort(key=lambda x: x[1], reverse=True)
        top_features = feature_scores[:top_n]
        
        # Create plot
        plt.figure(figsize=figsize)
        features, scores = zip(*top_features)
        
        plt.barh(range(len(features)), scores)
        plt.yticks(range(len(features)), features)
        plt.xlabel('Importance Score')
        plt.title(f'Top {top_n} Features - {importance_result.importance_method.title()} Importance')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.show()
    
    def create_feature_importance_summary(self,
                                        analysis_report: FeatureAnalysisReport) -> Dict[str, Any]:
        """
        Create a summary of feature importance analysis.
        
        Args:
            analysis_report: Complete analysis report
            
        Returns:
            Dictionary with summary statistics
        """
        
        summary = {
            'total_features': analysis_report.total_features,
            'consensus_features': len(analysis_report.consensus_features),
            'selection_ratio': analysis_report.selection_ratio,
            'methods_used': analysis_report.importance_methods,
            'top_consensus_features': analysis_report.consensus_features[:10],
            'highly_correlated_pairs': len(analysis_report.correlation_analysis['high_correlation_pairs']),
            'redundant_features': len(analysis_report.redundancy_analysis['redundant_features']),
            'feature_clusters': len(analysis_report.redundancy_analysis['feature_clusters'])
        }
        
        # Add method-specific top features
        for method, result in analysis_report.method_results.items():
            summary[f'{method}_top_features'] = result.top_features[:5]
        
        return summary