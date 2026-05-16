import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_products')
export class ComexstatProduct {
  @PrimaryColumn()
  flow: string;

  @PrimaryColumn()
  periodicity: string;

  @PrimaryColumn({ name: 'period_from' })
  periodFrom: string;

  @PrimaryColumn({ name: 'period_to' })
  periodTo: string;

  @PrimaryColumn()
  aggregation: string;

  @PrimaryColumn()
  code: string;

  @Column({ nullable: true, type: 'text' })
  description: string;

  @Column({ name: 'fob_value', type: 'numeric', nullable: true })
  fobValue: number;

  @Column({ name: 'weight_kg', type: 'numeric', nullable: true })
  weightKg: number;

  @Column({ type: 'numeric', nullable: true })
  share: number;
}
