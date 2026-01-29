import {
  Controller,
  Get,
  Post,
  HttpCode,
  HttpStatus,
  Query,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiQuery,
} from '@nestjs/swagger';
import { ScmService } from './scm.service';

@ApiTags('SCM - Sistema de Cadastro Mineiro')
@Controller('scm')
export class ScmController {
  constructor(private readonly scmService: ScmService) {}

  @Get('health')
  @ApiOperation({ summary: 'Verificar saúde do sistema SCM e status do banco de dados' })
  @ApiResponse({ status: 200, description: 'Status da saúde do sistema' })
  async getHealth() {
    try {
      const counts = await this.scmService.getDataCounts();
      return {
        status: 'healthy',
        database: 'connected',
        dataLoaded: counts.processos > 0,
        counts,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message,
        timestamp: new Date().toISOString(),
      };
    }
  }

  @Get('summary')
  @ApiOperation({ summary: 'Obter resumo dos dados SCM com contadores e analytics' })
  @ApiResponse({
    status: 200,
    description: 'Resumo dos dados obtido com sucesso',
  })
  async getDataSummary() {
    return this.scmService.getDataSummary();
  }

  @Get('processos')
  @ApiOperation({ summary: 'Obter todos os processos minerários' })
  @ApiResponse({ status: 200, description: 'Processos obtidos com sucesso' })
  @ApiQuery({
    name: 'limit',
    required: false,
    type: Number,
    description: 'Limitar número de resultados',
  })
  async getProcessos(@Query('limit') limit?: number) {
    const processos = await this.scmService.getProcessos();
    return limit ? processos.slice(0, limit) : processos;
  }

  @Get('fases')
  @ApiOperation({ summary: 'Obter todas as fases dos processos' })
  @ApiResponse({
    status: 200,
    description: 'Fases dos processos obtidas com sucesso',
  })
  async getFases() {
    return this.scmService.getFases();
  }

  @Get('tipos')
  @ApiOperation({ summary: 'Obter todos os tipos de requerimento' })
  @ApiResponse({
    status: 200,
    description: 'Tipos de requerimento obtidos com sucesso',
  })
  async getTipos() {
    return this.scmService.getTipos();
  }

  @Get('municipios')
  @ApiOperation({ summary: 'Obter todos os municípios' })
  @ApiResponse({
    status: 200,
    description: 'Municípios obtidos com sucesso',
  })
  async getMunicipios() {
    return this.scmService.getMunicipios();
  }

  @Get('substancias')
  @ApiOperation({ summary: 'Obter todas as substâncias/minerais' })
  @ApiResponse({
    status: 200,
    description: 'Substâncias obtidas com sucesso',
  })
  async getSubstancias() {
    return this.scmService.getSubstancias();
  }

  @Get('analytics/by-fase')
  @ApiOperation({ summary: 'Obter contagem de processos por fase' })
  @ApiResponse({
    status: 200,
    description: 'Analytics por fase obtidas com sucesso',
  })
  async getProcessosByFase() {
    return this.scmService.getProcessosByFase();
  }

  @Get('analytics/by-tipo')
  @ApiOperation({ summary: 'Obter contagem de processos por tipo de requerimento' })
  @ApiResponse({
    status: 200,
    description: 'Analytics por tipo obtidas com sucesso',
  })
  async getProcessosByTipo() {
    return this.scmService.getProcessosByTipo();
  }

  @Get('analytics/by-municipio')
  @ApiOperation({ summary: 'Obter contagem de processos por município' })
  @ApiResponse({
    status: 200,
    description: 'Analytics por município obtidas com sucesso',
  })
  async getProcessosByMunicipio() {
    return this.scmService.getProcessosByMunicipio();
  }

  @Get('analytics/by-substancia')
  @ApiOperation({ summary: 'Obter contagem de processos por substância/mineral' })
  @ApiResponse({
    status: 200,
    description: 'Analytics por substância obtidas com sucesso',
  })
  async getProcessosBySubstancia() {
    return this.scmService.getProcessosBySubstancia();
  }

  @Get('analytics/by-uf')
  @ApiOperation({ summary: 'Obter contagem de processos por estado (UF)' })
  @ApiResponse({
    status: 200,
    description: 'Analytics por estado obtidas com sucesso',
  })
  async getProcessosByUF() {
    return this.scmService.getProcessosByUF();
  }

  @Get('relations/processo-municipios')
  @ApiOperation({ summary: 'Obter relacionamentos processo-município' })
  @ApiResponse({
    status: 200,
    description: 'Relacionamentos processo-município obtidos com sucesso',
  })
  @ApiQuery({
    name: 'processo',
    required: false,
    type: String,
    description: 'Filtrar por ID do processo',
  })
  async getProcessoMunicipios(@Query('processo') processo?: string) {
    const relations = await this.scmService.getProcessoMunicipios();
    return processo
      ? relations.filter((r) => r.DSProcesso === processo)
      : relations;
  }

  @Get('relations/processo-substancias')
  @ApiOperation({ summary: 'Obter relacionamentos processo-substância' })
  @ApiResponse({
    status: 200,
    description: 'Relacionamentos processo-substância obtidos com sucesso',
  })
  @ApiQuery({
    name: 'processo',
    required: false,
    type: String,
    description: 'Filtrar por ID do processo',
  })
  async getProcessoSubstancias(@Query('processo') processo?: string) {
    const relations = await this.scmService.getProcessoSubstancias();
    return processo
      ? relations.filter((r) => r.DSProcesso === processo)
      : relations;
  }

  @Post('update')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Disparar atualização manual dos dados da ANM' })
  @ApiResponse({
    status: 200,
    description: 'Atualização dos dados disparada com sucesso',
  })
  @ApiResponse({ status: 500, description: 'Falha ao atualizar os dados' })
  async triggerUpdate() {
    await this.scmService.triggerManualUpdate();
    return { message: 'Atualização dos dados concluída com sucesso' };
  }

  @Get('search')
  @ApiOperation({ summary: 'Buscar processos com filtros' })
  @ApiResponse({ status: 200, description: 'Processos filtrados obtidos com sucesso' })
  @ApiQuery({ name: 'processo', required: false, type: String, description: 'Filtrar por ID do processo' })
  @ApiQuery({ name: 'municipio', required: false, type: Number, description: 'Filtrar por ID do município' })
  @ApiQuery({ name: 'substancia', required: false, type: Number, description: 'Filtrar por ID da substância' })
  @ApiQuery({ name: 'fase', required: false, type: Number, description: 'Filtrar por ID da fase' })
  @ApiQuery({ name: 'tipo', required: false, type: Number, description: 'Filtrar por ID do tipo de requerimento' })
  @ApiQuery({ name: 'limit', required: false, type: Number, description: 'Limitar número de resultados' })
  async searchProcessos(
    @Query('processo') processo?: string,
    @Query('municipio') municipio?: number,
    @Query('substancia') substancia?: number,
    @Query('fase') fase?: number,
    @Query('tipo') tipo?: number,
    @Query('limit') limit?: number,
  ) {
    return this.scmService.findProcessosByFilters({
      processo,
      municipio: municipio ? Number(municipio) : undefined,
      substancia: substancia ? Number(substancia) : undefined,
      fase: fase ? Number(fase) : undefined,
      tipo: tipo ? Number(tipo) : undefined,
      limit: limit ? Number(limit) : undefined,
    });
  }
}
