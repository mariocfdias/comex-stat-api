import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { Test, TestingModule } from '@nestjs/testing';
import axios from 'axios';
import { ComexstatService, COMEXSTAT_HTTP_CLIENT } from './comexstat.service';

describe('ComexstatService', () => {
  let service: ComexstatService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ComexstatService,
        {
          provide: COMEXSTAT_HTTP_CLIENT,
          useValue: axios.create(),
        },
        {
          provide: CACHE_MANAGER,
          useValue: {
            get: jest.fn(),
            set: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<ComexstatService>(ComexstatService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
