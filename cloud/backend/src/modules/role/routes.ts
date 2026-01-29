import { Router } from 'express';
import { RoleController } from './controller';

export function createRoleRoutes(controller: RoleController): Router {
  const router = Router();

  // 角色管理
  router.post('/', controller.createRole.bind(controller));
  router.get('/', controller.getAllRoles.bind(controller));
  router.get('/:uuid', controller.getRole.bind(controller));
  router.put('/:uuid', controller.updateRole.bind(controller));
  router.delete('/:uuid', controller.deleteRole.bind(controller));

  // 获取角色绑定的机器人
  router.get('/:uuid/robots', controller.getRobotsByRole.bind(controller));

  return router;
}
