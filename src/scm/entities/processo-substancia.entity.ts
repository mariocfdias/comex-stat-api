import { Entity, PrimaryColumn, Column, ManyToOne, JoinColumn } from 'typeorm';
import { Processo } from './processo.entity';
import { Substancia } from './substancia.entity';

@Entity('processo_substancia')
export class ProcessoSubstancia {
  @PrimaryColumn({ type: 'varchar', length: 50 })
  DSProcesso: string;

  @PrimaryColumn({ type: 'integer' })
  IDSubstancia: number;

  @Column({ type: 'integer', nullable: true })
  IDTipoUsoSubstancia: number;

  @Column({ type: 'integer', nullable: true })
  IDMotivoEncerramentoSubstancia: number;

  // Relationships
  @ManyToOne(() => Processo, processo => processo.processoSubstancias, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'DSProcesso' })
  processo?: Processo;

  @ManyToOne(() => Substancia, substancia => substancia.processoSubstancias)
  @JoinColumn({ name: 'IDSubstancia' })
  substancia?: Substancia;
}