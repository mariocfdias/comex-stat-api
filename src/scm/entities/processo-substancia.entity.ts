import { Entity, PrimaryColumn, Column, Index } from 'typeorm';

@Entity('scm_processo_substancia')
@Index(['IDSubstancia'])
export class ProcessoSubstancia {
  @PrimaryColumn({ name: 'ds_processo', type: 'varchar', length: 50 })
  DSProcesso: string;

  @PrimaryColumn({ name: 'id_substancia', type: 'integer' })
  IDSubstancia: number;

  @Column({ name: 'id_tipo_uso_substancia', type: 'integer', nullable: true })
  IDTipoUsoSubstancia: number;

  @Column({ name: 'id_motivo_encerramento_substancia', type: 'integer', nullable: true })
  IDMotivoEncerramentoSubstancia: number;
}
