import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_summary')
export class ComexstatSummary {
  @PrimaryColumn({ name: 'period_type' })
  periodType: string;

  @PrimaryColumn({ name: 'period_label' })
  periodLabel: string;

  @Column({ name: 'export_fob', type: 'numeric', nullable: true })
  exportFob: number;

  @Column({ name: 'import_fob', type: 'numeric', nullable: true })
  importFob: number;

  @Column({ name: 'balance', type: 'numeric', nullable: true })
  balance: number;

  @Column({ name: 'export_growth', type: 'numeric', nullable: true })
  exportGrowth: number;

  @Column({ name: 'import_growth', type: 'numeric', nullable: true })
  importGrowth: number;
}
