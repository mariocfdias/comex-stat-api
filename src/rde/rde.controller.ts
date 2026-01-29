import { Controller, Get, Query, ValidationPipe } from '@nestjs/common';
import {
  ApiExtraModels,
  ApiOkResponse,
  ApiOperation,
  ApiTags,
} from '@nestjs/swagger';
import {
  RdeQueryDto,
  TodosRegistrosDto,
  RegistrosIedDto,
  TodosRegistrosResponseDto,
  RegistrosIedResponseDto,
} from './dto/rde.dto';
import { RdeService } from './rde.service';

@ApiTags('rde')
@ApiExtraModels(
  TodosRegistrosResponseDto,
  RegistrosIedResponseDto,
  TodosRegistrosDto,
  RegistrosIedDto,
)
@Controller('rde')
export class RdeController {
  constructor(private readonly rdeService: RdeService) {}

  @Get('todos-registros')
  @ApiOperation({
    summary:
      'Consulta todos os registros RDE publicados (a partir de novembro de 2011)',
    description:
      'Retorna dados dos registros RDE para o Ceará com suporte a filtros OData. Por padrão, filtra apenas dados do Ceará.',
  })
  @ApiOkResponse({
    description: 'Registros RDE recuperados com sucesso.',
    type: TodosRegistrosResponseDto,
  })
  async getTodosRegistros(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: RdeQueryDto,
  ): Promise<TodosRegistrosResponseDto> {
    const result = await this.rdeService.getTodosRegistros(query);

    return {
      success: true,
      data: result.data,
      total: result.total,
    };
  }

  @Get('registros-ied')
  @ApiOperation({
    summary: 'Consulta registros RDE-IED com CNPJ Base da Receptora',
    description:
      'Retorna dados dos registros RDE-IED para o Ceará incluindo informação de CNPJ Base da Receptora. Por padrão, filtra apenas dados do Ceará.',
  })
  @ApiOkResponse({
    description: 'Registros RDE-IED recuperados com sucesso.',
    type: RegistrosIedResponseDto,
  })
  async getRegistrosIed(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: RdeQueryDto,
  ): Promise<RegistrosIedResponseDto> {
    const result = await this.rdeService.getRegistrosIed(query);

    return {
      success: true,
      data: result.data,
      total: result.total,
    };
  }
}
