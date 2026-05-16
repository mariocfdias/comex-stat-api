import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('scm_tipos')
export class TipoRequerimento {
  @PrimaryColumn({ name: 'id_tipo_requerimento', type: 'integer' })
  IDTipoRequerimento: number;

  @Column({ name: 'ds_tipo_requerimento', type: 'varchar', length: 200, nullable: true })
  DSTipoRequerimento: string;
}
