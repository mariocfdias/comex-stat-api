import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, IsOptional, IsPositive, IsString } from 'class-validator';

export class RdeQueryDto {
  @ApiPropertyOptional({
    type: String,
    description: 'Propriedades que serão retornadas',
  })
  @IsString()
  @IsOptional()
  select?: string;

  @ApiPropertyOptional({
    type: Number,
    description:
      'Índice (maior ou igual a zero) da primeira entidade que será retornada',
  })
  @Type(() => Number)
  @IsInt()
  @IsOptional()
  skip?: number;

  @ApiPropertyOptional({
    type: Number,
    default: 100,
    description:
      'Número máximo (maior que zero) de entidades que serão retornadas',
  })
  @Type(() => Number)
  @IsInt()
  @IsPositive()
  @IsOptional()
  top = 100;
}

export class TodosRegistrosDto {
  @ApiProperty({ description: 'Código RDE do registro' })
  CodigoRDE!: string;

  @ApiPropertyOptional({
    description: 'Nome da Pessoa Física Residente ou Jurídica Nacional',
  })
  NomePessoaNacional?: string;

  @ApiPropertyOptional({
    description: 'Unidade da Federação da Pessoa Nacional',
  })
  UfPessoaNacional?: string;

  @ApiPropertyOptional({ description: 'Nome da Pessoa Estrangeira' })
  NomePessoaEstrangeira?: string;

  @ApiPropertyOptional({ description: 'País da Pessoa Estrangeira' })
  PaisPessoaEstrangeira?: string;

  @ApiPropertyOptional({ description: 'Moeda da Operação registrada' })
  MoedaOperacao?: string;

  @ApiPropertyOptional({
    type: Number,
    description: 'Valor da Operação na moeda registrada',
  })
  ValorOperacao?: number;

  @ApiProperty({
    description: 'Módulo do Sistema RDE (RDE-ROF, RDE-IED ou RDE-PORTFOLIO)',
  })
  Sistema!: string;

  @ApiProperty({ description: 'Ocorrência do registro' })
  Ocorrencia!: string;

  @ApiProperty({ description: 'Modalidade do Registro' })
  Modalidade!: string;

  @ApiProperty({
    type: Number,
    description: 'Ano da Ocorrência',
  })
  Ano!: number;

  @ApiProperty({
    type: Number,
    description: 'Mês da Ocorrência',
  })
  Mes!: number;
}

export class RegistrosIedDto {
  @ApiProperty({ description: 'Código RDE do registro' })
  CodigoRDE!: string;

  @ApiProperty({ description: 'CNPJ Base da Receptora' })
  CnpjBaseReceptora!: string;

  @ApiProperty({ description: 'Nome da Pessoa Jurídica Nacional' })
  NomePessoaNacional!: string;

  @ApiPropertyOptional({
    description: 'Unidade da Federação da Pessoa Nacional',
  })
  UfPessoaNacional?: string;

  @ApiPropertyOptional({ description: 'Nome da Pessoa Estrangeira' })
  NomePessoaEstrangeira?: string;

  @ApiPropertyOptional({ description: 'País da Pessoa Estrangeira' })
  PaisPessoaEstrangeira?: string;

  @ApiPropertyOptional({ description: 'Moeda da Operação registrada' })
  MoedaOperacao?: string;

  @ApiPropertyOptional({
    type: Number,
    description: 'Valor da Operação na moeda registrada',
  })
  ValorOperacao?: number;

  @ApiProperty({
    description: 'Módulo do Sistema RDE (RDE-ROF, RDE-IED ou RDE-PORTFOLIO)',
  })
  Sistema!: string;

  @ApiProperty({ description: 'Ocorrência do registro' })
  Ocorrencia!: string;

  @ApiProperty({ description: 'Modalidade do Registro' })
  Modalidade!: string;

  @ApiProperty({
    type: Number,
    description: 'Ano da Ocorrência',
  })
  Ano!: number;

  @ApiProperty({
    type: Number,
    description: 'Mês da Ocorrência',
  })
  Mes!: number;
}

export interface RdeODataResponse<T> {
  '@odata.context': string;
  value: T[];
}

export class TodosRegistrosResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: [TodosRegistrosDto] })
  data!: TodosRegistrosDto[];

  @ApiPropertyOptional()
  total?: number;
}

export class RegistrosIedResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: [RegistrosIedDto] })
  data!: RegistrosIedDto[];

  @ApiPropertyOptional()
  total?: number;
}
