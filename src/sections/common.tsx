import React from "react";


export interface SectionProps {
    setHeading: (name:string) => void;
    displayProgressBar: (isBusy: boolean) => void;
}

export abstract class AbstractSection<P = {}, S = {}, SS = {}> extends React.Component<P & SectionProps, S, SS> {

    abstract sectionName():string;

    componentDidMount() {
        this.props.setHeading(this.sectionName());
    }
}