import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { SkillCategoryPublic, SkillPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteSkill from "@/components/Skills/DeleteSkill"
import EditSkill from "@/components/Skills/EditSkill"
import ReplaceSkillFile from "@/components/Skills/ReplaceSkillFile"
import ToggleSkillPublish from "@/components/Skills/ToggleSkillPublish"

interface SkillActionsMenuProps {
  categories: SkillCategoryPublic[]
  skill: SkillPublic
}

const SkillActionsMenu = ({ categories, skill }: SkillActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditSkill categories={categories} skill={skill} />
        <ReplaceSkillFile skill={skill} />
        <ToggleSkillPublish skill={skill} />
        <DeleteSkill skill={skill} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default SkillActionsMenu
