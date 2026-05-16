import { Entity, PrimaryColumn, Index } from 'typeorm';

@Entity('scm_processo_municipio')
@Index(['IDMunicipio'])
@Index(['DSProcesso'])
export class ProcessoMunicipio {
  @PrimaryColumn({ name: 'ds_processo', type: 'varchar', length: 50 })
  DSProcesso: string;

  @PrimaryColumn({ name: 'id_municipio', type: 'integer' })
  IDMunicipio: number;
}
