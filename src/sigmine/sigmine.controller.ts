import { Controller, Get } from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import {
  SigmineLayer,
  type LayerGeoJsonDto,
} from './dto/sigmine-layer.dto';
import { SigmineService } from './sigmine.service';

@ApiTags('layers')
@Controller('layers')
export class SigmineController {
  constructor(private readonly sigmineService: SigmineService) {}

  @Get('area-servidao')
  @ApiOperation({ summary: 'Retorna o GeoJSON de AREA_SERVIDAO.' })
  getAreaServidao(): Promise<LayerGeoJsonDto> {
    return this.sigmineService.getLayer(SigmineLayer.AREA_SERVIDAO);
  }

  @Get('arrendamento')
  @ApiOperation({ summary: 'Retorna o GeoJSON de ARRENDAMENTO.' })
  getArrendamento(): Promise<LayerGeoJsonDto> {
    return this.sigmineService.getLayer(SigmineLayer.ARRENDAMENTO);
  }

  @Get('bloqueio')
  @ApiOperation({ summary: 'Retorna o GeoJSON de BLOQUEIO.' })
  getBloqueio(): Promise<LayerGeoJsonDto> {
    return this.sigmineService.getLayer(SigmineLayer.BLOQUEIO);
  }

  @Get('ce')
  @ApiOperation({ summary: 'Retorna o GeoJSON de CE (Processos Minerais).' })
  getCe(): Promise<LayerGeoJsonDto> {
    return this.sigmineService.getLayer(SigmineLayer.CE);
  }

  @Get('protecao-fonte')
  @ApiOperation({ summary: 'Retorna o GeoJSON de PROTECAO_FONTE.' })
  getProtecaoFonte(): Promise<LayerGeoJsonDto> {
    return this.sigmineService.getLayer(SigmineLayer.PROTECAO_FONTE);
  }

  @Get('reservas-garimpeiras')
  @ApiOperation({ summary: 'Retorna o GeoJSON de RESERVAS_GARIMPEIRAS.' })
  getReservasGarimpeiras(): Promise<LayerGeoJsonDto> {
    return this.sigmineService.getLayer(SigmineLayer.RESERVAS_GARIMPEIRAS);
  }
}
