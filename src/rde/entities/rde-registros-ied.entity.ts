import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('rde_registros_ied')
export class RdeRegistrosIed {
  @PrimaryColumn({ name: 'codigo_rde' })
  CodigoRDE: string;

  @Column({ name: 'cnpj_base_receptora', nullable: true })
  CnpjBaseReceptora: string;

  @Column({ name: 'nome_pessoa_nacional', nullable: true })
  NomePessoaNacional: string;

  @Column({ name: 'uf_pessoa_nacional', nullable: true })
  UfPessoaNacional: string;

  @Column({ name: 'nome_pessoa_estrangeira', nullable: true })
  NomePessoaEstrangeira: string;

  @Column({ name: 'pais_pessoa_estrangeira', nullable: true })
  PaisPessoaEstrangeira: string;

  @Column({ name: 'moeda_operacao', nullable: true })
  MoedaOperacao: string;

  @Column({ name: 'valor_operacao', type: 'numeric', nullable: true })
  ValorOperacao: number;

  @Column({ nullable: true })
  Sistema: string;

  @Column({ nullable: true })
  Ocorrencia: string;

  @Column({ nullable: true })
  Modalidade: string;

  @Column({ type: 'integer', nullable: true })
  Ano: number;

  @Column({ type: 'integer', nullable: true })
  Mes: number;
}
