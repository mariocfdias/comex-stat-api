import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('sigmine_layers')
export class SigmineLayerEntity {
  @PrimaryColumn({ name: 'layer_name' })
  layerName: string;

  @Column({ type: 'jsonb' })
  geojson: object;

  @Column({ name: 'feature_count', type: 'integer', nullable: true })
  featureCount: number;
}
