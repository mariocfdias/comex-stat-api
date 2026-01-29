import { Module } from '@nestjs/common';
import axios from 'axios';
import { Agent } from 'node:https';
import { RdeController } from './rde.controller';
import { RdeService, RDE_HTTP_CLIENT } from './rde.service';

@Module({
  controllers: [RdeController],
  providers: [
    {
      provide: RDE_HTTP_CLIENT,
      useFactory: () =>
        axios.create({
          baseURL:
            'https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata',
          timeout: 60_000,
          headers: {
            Accept: 'application/json;odata.metadata=minimal',
          },
          httpsAgent: new Agent({
            rejectUnauthorized: process.env.RDE_ALLOW_INSECURE !== 'false',
          }),
        }),
    },
    RdeService,
  ],
  exports: [RdeService],
})
export class RdeModule {}
