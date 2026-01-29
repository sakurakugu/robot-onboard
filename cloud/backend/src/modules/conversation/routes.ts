import { Router } from 'express';
import { ConversationController } from './controller';

export function createConversationRoutes(controller: ConversationController): Router {
  const router = Router();

  router.get('/:robotId', controller.getHistory.bind(controller));
  router.post('/:robotId/command', controller.sendCommand.bind(controller));

  return router;
}
