import { Router } from 'express';
import { SettingsController } from './controller';

export function createSettingsRoutes(controller: SettingsController): Router {
  const router = Router();

  // LLM配置
  router.get('/llm', controller.getLLMConfig.bind(controller));
  router.get('/llm/providers', controller.getLLMProviders.bind(controller));
  router.put('/llm', controller.updateLLMConfig.bind(controller));
  router.get('/params', controller.getParams.bind(controller));
  router.put('/params', controller.updateParams.bind(controller));

  // UI配置
  router.get('/ui', controller.getUIConfig.bind(controller));
  router.put('/ui', controller.updateUIConfig.bind(controller));

  return router;
}
