import { AbstractSection, SectionProps } from '../common';
import { Box, Tab, Tabs, Card } from '@mui/material';
import { Trades } from './add/Trades';
import { Values } from "./add/Values";
import { Dividends } from "./add/Dividends";
import { Deposits } from './add/Deposits';
import { Staking } from './add/Staking';

interface AddState {
    tab: number;
}

interface AddProps {}

export class Add extends AbstractSection<AddProps, AddState> {

    sectionName = () => 'Add';

    constructor(props:AddProps & SectionProps) {
        super(props);
        this.state = {tab: 0};
    }

    render() {

        return <Box>
            <Card sx={{marginBottom: '1em'}}>
                <Tabs value={this.state.tab} onChange={(_, v) => this.setState({tab: v})} aria-label="basic tabs example">
                    <Tab label="Trades" value={0}/>
                    <Tab label="Deposits" value={1}/>
                    <Tab label="Values" value={2}/>
                    <Tab label="Dividends" value={3}/>
                    <Tab label="Staking" value={4}/>
                </Tabs>
            </Card>
            <Card>
                {this.state.tab === 0 ?
                    <Trades config={this.props.config} setHeading={this.props.setHeading} displayProgressBar={this.props.displayProgressBar} /> : null}
                {this.state.tab === 1 ?
                    <Deposits config={this.props.config} setHeading={this.props.setHeading} displayProgressBar={this.props.displayProgressBar} /> : null}
                {this.state.tab === 2 ?
                    <Values config={this.props.config} setHeading={this.props.setHeading} displayProgressBar={this.props.displayProgressBar} /> : null}
                {this.state.tab === 3 ?
                    <Dividends config={this.props.config} setHeading={this.props.setHeading} displayProgressBar={this.props.displayProgressBar} /> : null}
                {this.state.tab === 4 ?
                    <Staking config={this.props.config} setHeading={this.props.setHeading} displayProgressBar={this.props.displayProgressBar} /> : null}
            </Card>
        </Box>
    }
}