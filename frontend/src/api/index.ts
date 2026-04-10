export { default as api } from './client'
export { authApi } from './auth'
export { dataApi } from './data'
export { trainApi } from './train'
export { experimentApi } from './experiments'
export { vizApi } from './viz'

export type { LoginRequest, RegisterRequest, AuthResponse, User } from './auth'
export type { DataFile } from './data'
export type { TrainRequest, TrainJob, TrainStatus } from './train'
export type { Experiment, MetricsHistory } from './experiments'
export type {
  DistributionStats, FeatureDistribution, DataDistributionsResponse, DataSummary,
  FeatureImportanceItem, FeatureImportanceResponse,
  EvaluationResponse, TrainingCurve, TrainingCurvesResponse
} from './viz'
