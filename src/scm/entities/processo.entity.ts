import { Entity, PrimaryColumn, Column, ManyToOne, OneToMany, JoinColumn, Index } from 'typeorm';
import { FaseProcesso } from './fase-processo.entity';
import { TipoRequerimento } from './tipo-requerimento.entity';
import { ProcessoMunicipio } from './processo-municipio.entity';
import { ProcessoSubstancia } from './processo-substancia.entity';

@Entity('processos')
@Index(['IDFaseProcesso'])
@Index(['IDTipoRequerimento'])
export class Processo {
  @PrimaryColumn({ type: 'varchar', length: 50 })
  DSProcesso: string;

  @Column({ type: 'varchar', length: 20, nullable: true })
  NRProcesso: string;

  @Column({ type: 'varchar', length: 4, nullable: true })
  NRAnoProcesso: string;

  @Column({ type: 'varchar', length: 1, nullable: true })
  BTAtivo: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  NRNUP: string;

  @Column({ type: 'integer', nullable: true })
  IDTipoRequerimento: number;

  @Column({ type: 'integer', nullable: true })
  IDFaseProcesso: number;

  @Column({ type: 'integer', nullable: true })
  IDUnidadeAdministrativaRegional: number;

  @Column({ type: 'integer', nullable: true })
  IDUnidadeProtocolizadora: number;

  @Column({ type: 'varchar', length: 30, nullable: true })
  DTProtocolo: string;

  @Column({ type: 'varchar', length: 30, nullable: true })
  DTPrioridade: string;

  @Column({ type: 'varchar', length: 20, nullable: true })
  QTAreaHA: string;

  // Relationships
  @ManyToOne(() => FaseProcesso, { nullable: true, lazy: true })
  @JoinColumn({ name: 'IDFaseProcesso' })
  fase?: FaseProcesso;

  @ManyToOne(() => TipoRequerimento, { nullable: true, lazy: true })
  @JoinColumn({ name: 'IDTipoRequerimento' })
  tipo?: TipoRequerimento;

  @OneToMany(() => ProcessoMunicipio, pm => pm.processo, { lazy: true })
  processoMunicipios?: ProcessoMunicipio[];

  @OneToMany(() => ProcessoSubstancia, ps => ps.processo, { lazy: true })
  processoSubstancias?: ProcessoSubstancia[];
}