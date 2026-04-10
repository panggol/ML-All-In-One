export { default as api } from './client'
export { authApi } from './auth'
export { dataApi } from './data'
export { trainApi } from './train'
export { experimentApi } from './experiments'
export { vizApi } from './viz'

export type { LoginRequest, RegisterRequest, AuthResponse, User } from './auth'
export type { DataFile } from './data'
export type { TrainRequest, TrainJob, TrainStatus, MetricsCurve } from './train'
export type { Experiment, MetricsHistory } from './experiments'
export type {
  DistributionStats, FeatureDistribution, DataDistributionsResponse, DataSummary,
  FeatureImportanceItem, FeatureImportanceResponse,
  EvaluationResponse, TrainingCurve, TrainingCurvesResponse
} from './viz'
export { automlApi } from './automl'
export { preprocessingApi, DEFAULT_STEPS } from './preprocessing'
export { modelsApi } from './models'
export type { ModelInfo, InferenceResult } from './models'
export type {
  AutoMLRequest, AutoMLStatus, AutoMLReport, SearchSpaceItem, TopModel
} from './automl'
export type {
  ImputerConfig, ScalerConfig, FeatureSelectConfig, PreprocessingSteps,
  ColumnStats, PreviewResponse, TransformResponse
} from './preprocessing'

