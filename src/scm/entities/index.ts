// TypeORM Entities
export { Processo } from './processo.entity';
export { FaseProcesso } from './fase-processo.entity';
export { TipoRequerimento } from './tipo-requerimento.entity';
export { Municipio } from './municipio.entity';
export { Substancia } from './substancia.entity';
export { ProcessoMunicipio } from './processo-municipio.entity';
export { ProcessoSubstancia } from './processo-substancia.entity';

// Legacy interfaces (for compatibility)
export interface ProcessoEntity {
  DSProcesso: string;
  NRProcesso: string;
  NRAnoProcesso: string;
  BTAtivo: string;
  NRNUP: string;
  IDTipoRequerimento: number;
  IDFaseProcesso: number;
  IDUnidadeAdministrativaRegional: number;
  IDUnidadeProtocolizadora: number;
  DTProtocolo: string;
  DTPrioridade: string;
  QTAreaHA: string;
}

export interface FaseProcessoEntity {
  IDFaseProcesso: number;
  DSFaseProcesso: string;
}

export interface TipoRequerimentoEntity {
  IDTipoRequerimento: number;
  DSTipoRequerimento: string;
}

export interface MunicipioEntity {
  IDMunicipio: number;
  NMMunicipio: string;
  SGUF: string;
}

export interface SubstanciaEntity {
  IDSubstancia: number;
  NMSubstancia: string;
}

export interface ProcessoMunicipioEntity {
  DSProcesso: string;
  IDMunicipio: number;
}

export interface ProcessoSubstanciaEntity {
  DSProcesso: string;
  IDSubstancia: number;
  IDTipoUsoSubstancia: number;
  IDMotivoEncerramentoSubstancia: number;
}