import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_partners')
export class ComexstatPartner {
  @PrimaryColumn()
  flow: string;

  @PrimaryColumn({ name: 'period_from' })
  periodFrom: string;

  @PrimaryColumn({ name: 'period_to' })
  periodTo: string;

  @PrimaryColumn({ name: 'country_code' })
  countryCode: string;

  @Column({ name: 'country_name', nullable: true })
  countryName: string;

  @Column({ name: 'fob_value', type: 'numeric', nullable: true })
  fobValue: number;

  @Column({ type: 'numeric', nullable: true })
  share: number;

  @Column({ type: 'integer', nullable: true })
  ranking: number;
}
