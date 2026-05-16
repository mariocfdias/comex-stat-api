import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_national')
export class ComexstatNational {
  @PrimaryColumn()
  flow: string;

  @PrimaryColumn({ name: 'period_from' })
  periodFrom: string;

  @PrimaryColumn({ name: 'period_to' })
  periodTo: string;

  @Column({ name: 'ceara_fob', type: 'numeric', nullable: true })
  cearaFob: number;

  @Column({ name: 'brazil_fob', type: 'numeric', nullable: true })
  brazilFob: number;

  @Column({ name: 'ceara_share', type: 'numeric', nullable: true })
  cearaShare: number;

  @Column({ name: 'ceara_rank', type: 'integer', nullable: true })
  cearaRank: number;
}
