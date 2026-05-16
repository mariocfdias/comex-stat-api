import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_timeseries')
export class ComexstatTimeseries {
  @PrimaryColumn()
  periodicity: string;

  @PrimaryColumn()
  series: string;

  @PrimaryColumn({ type: 'integer' })
  year: number;

  @PrimaryColumn({ type: 'integer' })
  month: number;

  @Column({ type: 'numeric', nullable: true })
  value: number;
}
