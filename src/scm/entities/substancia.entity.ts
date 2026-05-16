import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('scm_substancias')
export class Substancia {
  @PrimaryColumn({ name: 'id_substancia', type: 'integer' })
  IDSubstancia: number;

  @Column({ name: 'nm_substancia', type: 'varchar', length: 200, nullable: true })
  NMSubstancia: string;
}
