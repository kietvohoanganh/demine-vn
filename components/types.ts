export type PriorityRow = {
  rank: number;
  cell_id: string;
  longitude: number;
  latitude: number;
  priority_score: number;
  priority_level: string;
  airstrike_evidence_score: number;
  crater_evidence_score: number;
  evidence_pattern: string;
  airstrike_records: number;
  airstrike_record_density: number | null;
  recorded_weapons_density: number | null;
  baseline_score?: number;
  population_count?: number | null;
  craters_in_cell: number;
  craters_within_300m: number;
  crater_density_per_km2: number;
  mean_crater_diameter_m: number | null;
  field_verified: boolean;
  is_probability: boolean;
};

export type FigureInfo = {file:string; title:string; caption:string};
export type SourceInfo = {label:string; technical:string};
export type GroundTruthInfo = {
  available:boolean;
  field_verified:boolean;
  spatial_layers_loaded:number;
  message:string;
  validation_role?:string;
  confirmed_hazard_cells?:number;
  released_cells?:number;
  eod_cells?:number;
  validated_cells?:number;
  cha_coverage_top10?:number|null;
  cha_coverage_top20?:number|null;
  eod_coverage_top10?:number|null;
  eod_coverage_top20?:number|null;
};
export type Results = {
  lookup_sha256?: string;
  mode: string;
  title: string;
  question: string;
  cells: number;
  airstrike_records_in_aoi: number;
  recorded_weapons_in_aoi: number;
  craters_in_aoi: number;
  cells_with_craters: number;
  priority_score_max: number;
  top20_evidence_coverage: number;
  field_verified: boolean;
  is_probability: boolean;
  grid_resolution_m: number;
  hotspot_spacing_m: number;
  sources: SourceInfo[];
  figures: FigureInfo[];
  warning: string;
  ground_truth: GroundTruthInfo;
};

export type AIComparison = {id:string;label:string;coverage_10:number;coverage_20:number;coverage_30:number};
export type AIResults = {
  status:string;model:string;model_sha256:string;trained_at:string;cells:number;base_lookup_sha256:string;
  population_valid_cells:number;
  source:string;source_retrieved_at:string;
  audit:{input_records:number;retained_records:number;recorded_cells:number;background_cells:number;unique_tasks:number};
  evaluation:{
    comparison:AIComparison[];delta_20:number;delta_20_interval:number[];
    folds:Array<{fold:number;name:string;train_cells:number;test_cells:number;test_recorded_cells:number;metrics:Record<string,Record<string,number>>}>;
    feature_importance:Array<{feature:string;label:string;coverage_drop_20:number}>;
  };
  limitations:string[];
};
