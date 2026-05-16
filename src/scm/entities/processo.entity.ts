import { Entity, PrimaryColumn, Column, Index } from 'typeorm';

@Entity('scm_processos')
@Index(['IDFaseProcesso'])
@Index(['IDTipoRequerimento'])
export class Processo {
  @PrimaryColumn({ name: 'ds_processo', type: 'varchar', length: 50 })
  DSProcesso: string;

  @Column({ name: 'nr_processo', type: 'varchar', length: 20, nullable: true })
  NRProcesso: string;

  @Column({ name: 'nr_ano_processo', type: 'varchar', length: 4, nullable: true })
  NRAnoProcesso: string;

  @Column({ name: 'bt_ativo', type: 'varchar', length: 1, nullable: true })
  BTAtivo: string;

  @Column({ name: 'nr_nup', type: 'varchar', length: 100, nullable: true })
  NRNUP: string;

  @Column({ name: 'id_tipo_requerimento', type: 'integer', nullable: true })
  IDTipoRequerimento: number;

  @Column({ name: 'id_fase_processo', type: 'integer', nullable: true })
  IDFaseProcesso: number;

  @Column({ name: 'id_unidade_administrativa_regional', type: 'integer', nullable: true })
  IDUnidadeAdministrativaRegional: number;

  @Column({ name: 'id_unidade_protocolizadora', type: 'integer', nullable: true })
  IDUnidadeProtocolizadora: number;

  @Column({ name: 'dt_protocolo', type: 'varchar', length: 30, nullable: true })
  DTProtocolo: string;

  @Column({ name: 'dt_prioridade', type: 'varchar', length: 30, nullable: true })
  DTPrioridade: string;

  @Column({ name: 'qt_area_ha', type: 'varchar', length: 20, nullable: true })
  QTAreaHA: string;
}
