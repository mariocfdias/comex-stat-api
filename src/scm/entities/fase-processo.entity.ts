import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('scm_fases')
export class FaseProcesso {
  @PrimaryColumn({ name: 'id_fase_processo', type: 'integer' })
  IDFaseProcesso: number;

  @Column({ name: 'ds_fase_processo', type: 'varchar', length: 200, nullable: true })
  DSFaseProcesso: string;
}
