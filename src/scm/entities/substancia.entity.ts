import { Entity, PrimaryColumn, Column, OneToMany } from 'typeorm';
import { ProcessoSubstancia } from './processo-substancia.entity';

@Entity('substancias')
export class Substancia {
  @PrimaryColumn({ type: 'integer' })
  IDSubstancia: number;

  @Column({ type: 'varchar', length: 200, nullable: true })
  NMSubstancia: string;

  // Relationships
  @OneToMany(() => ProcessoSubstancia, ps => ps.substancia)
  processoSubstancias?: ProcessoSubstancia[];
}