import { Entity, PrimaryColumn, Column, Index } from 'typeorm';

@Entity('scm_municipios')
@Index(['SGUF'])
export class Municipio {
  @PrimaryColumn({ name: 'id_municipio', type: 'integer' })
  IDMunicipio: number;

  @Column({ name: 'nm_municipio', type: 'varchar', length: 200, nullable: true })
  NMMunicipio: string;

  @Column({ name: 'sg_uf', type: 'varchar', length: 2, nullable: true })
  SGUF: string;
}
