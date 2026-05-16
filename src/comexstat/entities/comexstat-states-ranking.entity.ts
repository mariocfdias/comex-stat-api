import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('comexstat_states_ranking')
export class ComexstatStatesRanking {
  @PrimaryColumn()
  flow: string;

  @PrimaryColumn({ name: 'period_from' })
  periodFrom: string;

  @PrimaryColumn({ name: 'period_to' })
  periodTo: string;

  @PrimaryColumn({ name: 'state_code' })
  stateCode: string;

  @Column({ name: 'state_name', nullable: true })
  stateName: string;

  @Column({ name: 'fob_value', type: 'numeric', nullable: true })
  fobValue: number;

  @Column({ type: 'numeric', nullable: true })
  share: number;

  @Column({ type: 'integer', nullable: true })
  ranking: number;

  @Column({ type: 'jsonb', nullable: true })
  sectors: object;

  @Column({ name: 'top_partners', type: 'jsonb', nullable: true })
  topPartners: object;

  @Column({ name: 'top_products', type: 'jsonb', nullable: true })
  topProducts: object;
}
