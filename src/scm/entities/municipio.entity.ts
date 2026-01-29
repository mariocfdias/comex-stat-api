import { Entity, PrimaryColumn, Column, OneToMany } from 'typeorm';
import { ProcessoMunicipio } from './processo-municipio.entity';

@Entity('municipios')
export class Municipio {
  @PrimaryColumn({ type: 'integer' })
  IDMunicipio: number;

  @Column({ type: 'varchar', length: 200, nullable: true })
  NMMunicipio: string;

  @Column({ type: 'varchar', length: 2, nullable: true })
  SGUF: string;

  // Relationships
  @OneToMany(() => ProcessoMunicipio, pm => pm.municipio)
  processoMunicipios?: ProcessoMunicipio[];
}