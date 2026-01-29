import { Entity, PrimaryColumn, ManyToOne, JoinColumn } from 'typeorm';
import { Processo } from './processo.entity';
import { Municipio } from './municipio.entity';

@Entity('processo_municipio')
export class ProcessoMunicipio {
  @PrimaryColumn({ type: 'varchar', length: 50 })
  DSProcesso: string;

  @PrimaryColumn({ type: 'integer' })
  IDMunicipio: number;

  // Relationships
  @ManyToOne(() => Processo, processo => processo.processoMunicipios, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'DSProcesso' })
  processo?: Processo;

  @ManyToOne(() => Municipio, municipio => municipio.processoMunicipios)
  @JoinColumn({ name: 'IDMunicipio' })
  municipio?: Municipio;
}