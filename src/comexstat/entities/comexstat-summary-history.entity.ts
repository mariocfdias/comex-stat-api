import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_summary_history')
export class ComexstatSummaryHistory {
  @PrimaryColumn({ type: 'integer' })
  year: number;

  @PrimaryColumn({ type: 'integer' })
  month: number;

  @Column({ name: 'export_fob', type: 'numeric', nullable: true })
  exportFob: number;

  @Column({ name: 'import_fob', type: 'numeric', nullable: true })
  importFob: number;

  @Column({ type: 'numeric', nullable: true })
  balance: number;
}
