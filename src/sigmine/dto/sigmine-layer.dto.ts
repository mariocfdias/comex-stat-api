import type {
  FeatureCollection,
  GeoJsonProperties,
  Geometry,
} from 'geojson';

export type LayerGeoJsonDto = FeatureCollection<
  Geometry,
  GeoJsonProperties
>;

export enum SigmineLayer {
  AREA_SERVIDAO = 'area-servidao',
  ARRENDAMENTO = 'arrendamento',
  BLOQUEIO = 'bloqueio',
  CE = 'ce',
  PROTECAO_FONTE = 'protecao-fonte',
  RESERVAS_GARIMPEIRAS = 'reservas-garimpeiras',
}

export const SIGMINE_LAYER_SHAPEFILES: Record<SigmineLayer, string> = {
  [SigmineLayer.AREA_SERVIDAO]: 'AREA_SERVIDAO/AREA_SERVIDAO.shp',
  [SigmineLayer.ARRENDAMENTO]: 'ARRENDAMENTO/ARRENDAMENTO.shp',
  [SigmineLayer.BLOQUEIO]: 'BLOQUEIO/BLOQUEIO.shp',
  [SigmineLayer.CE]: 'CE/CE.shp',
  [SigmineLayer.PROTECAO_FONTE]: 'PROTECAO_FONTE/PROTECAO_FONTE.shp',
  [SigmineLayer.RESERVAS_GARIMPEIRAS]: 'RESERVAS_GARIMPEIRAS/RESERVAS_GARIMPEIRAS.shp',
};
