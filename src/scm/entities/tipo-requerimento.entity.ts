import { Entity, PrimaryColumn, Column, OneToMany } from 'typeorm';
import { Processo } from './processo.entity';

@Entity('tipo_requerimento')
export class TipoRequerimento {
  @PrimaryColumn({ type: 'integer' })
  IDTipoRequerimento: number;

  @Column({ type: 'varchar', length: 200, nullable: true })
  DSTipoRequerimento: string;

  // Relationships
  @OneToMany(() => Processo, processo => processo.tipo)
  processos?: Processo[];
}