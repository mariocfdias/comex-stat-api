import { Entity, PrimaryColumn, Column, OneToMany } from 'typeorm';
import { Processo } from './processo.entity';

@Entity('fase_processo')
export class FaseProcesso {
  @PrimaryColumn({ type: 'integer' })
  IDFaseProcesso: number;

  @Column({ type: 'varchar', length: 200, nullable: true })
  DSFaseProcesso: string;

  // Relationships
  @OneToMany(() => Processo, processo => processo.fase)
  processos?: Processo[];
}